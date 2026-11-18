"""Shared HTTP error helpers and FastAPI exception handlers."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("clipforge.errors")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if not isinstance(detail, str):
            detail = str(detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        # Prefer a short human-readable first error when possible
        message = "Validation failed"
        if errors:
            first = errors[0]
            loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
            msg = first.get("msg", message)
            message = f"{loc}: {msg}" if loc else msg
        # ctx may contain non-JSON-serializable exception objects
        safe_errors = []
        for err in errors:
            item = {k: v for k, v in err.items() if k != "ctx"}
            ctx = err.get("ctx")
            if isinstance(ctx, dict):
                item["ctx"] = {k: str(v) for k, v in ctx.items()}
            safe_errors.append(item)
        return JSONResponse(
            status_code=422,
            content={"detail": message, "errors": safe_errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("Unhandled server error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
