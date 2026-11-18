"""HTTP Range helpers for reliable HTML5 video seeking."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from starlette.responses import FileResponse

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def range_file_response(
    path: Path,
    request: Request,
    *,
    media_type: str,
    filename: str | None = None,
) -> Response:
    """
    Serve a file with proper Accept-Ranges / 206 Partial Content support.

    Starlette FileResponse supports ranges, but we handle the common single-range
    case explicitly so seeking works consistently across browsers.
    """
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    content_disposition = None
    if filename:
        content_disposition = f'inline; filename="{filename}"'

    if not range_header:
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        }
        if content_disposition:
            headers["Content-Disposition"] = content_disposition
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename,
            headers={"Accept-Ranges": "bytes"},
        )

    match = _RANGE_RE.match(range_header.strip())
    if not match:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    start_s, end_s = match.groups()
    try:
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
    except ValueError:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    if end_s == "" and start_s:
        end = file_size - 1
    if start_s == "" and end_s:
        # suffix bytes: last N bytes
        suffix = int(end_s)
        start = max(file_size - suffix, 0)
        end = file_size - 1

    if start >= file_size or end >= file_size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    length = end - start + 1

    def iter_file(chunk_size: int = 1024 * 1024):
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(length),
    }
    if content_disposition:
        headers["Content-Disposition"] = content_disposition

    return StreamingResponse(
        iter_file(),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )
