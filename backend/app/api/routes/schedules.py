from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleRead,
    YouTubeChannelStats,
    YouTubeConnectResponse,
    YouTubeShortsListResponse,
    YouTubeStatus,
)
from app.services import schedule_service, youtube_service
from app.services.schedule_service import ScheduleServiceError
from app.services.youtube_service import YouTubeServiceError

router = APIRouter(prefix="/api", tags=["schedules", "youtube"])
settings = get_settings()


@router.get("/youtube/status", response_model=YouTubeStatus)
def youtube_status():
    return youtube_service.get_public_status()


@router.post("/youtube/connect", response_model=YouTubeConnectResponse)
def youtube_connect():
    if not youtube_service.oauth_configured():
        return YouTubeConnectResponse(
            auth_url=None,
            configured=False,
            message=(
                "YouTube OAuth credentials are not set yet. Add GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET to backend/.env, register the redirect URI, then try again. "
                "You can complete the rest of ClipForge and connect later."
            ),
        )
    try:
        data = youtube_service.build_auth_url()
        return YouTubeConnectResponse(
            auth_url=data["auth_url"],
            state=data["state"],
            configured=True,
            message="Open the auth URL to connect your YouTube channel.",
        )
    except YouTubeServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/youtube/callback")
def youtube_callback(code: str | None = None, error: str | None = None):
    frontend = settings.frontend_url.rstrip("/")
    if error:
        return RedirectResponse(f"{frontend}/settings?youtube=error&reason={error}")
    if not code:
        return RedirectResponse(f"{frontend}/settings?youtube=error&reason=missing_code")
    try:
        youtube_service.exchange_code(code)
        return RedirectResponse(f"{frontend}/settings?youtube=connected")
    except Exception as exc:  # noqa: BLE001
        return RedirectResponse(
            f"{frontend}/settings?youtube=error&reason=exchange_failed"
        )


@router.post("/youtube/disconnect")
def youtube_disconnect():
    youtube_service.disconnect()
    return {"connected": False}


@router.get("/youtube/analytics/channel", response_model=YouTubeChannelStats)
def youtube_channel_analytics():
    try:
        return youtube_service.fetch_channel_stats()
    except YouTubeServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/youtube/analytics/shorts", response_model=YouTubeShortsListResponse)
def youtube_shorts_analytics(
    max_results: int = Query(default=25, ge=1, le=50),
    page_token: str | None = Query(default=None),
):
    try:
        return youtube_service.list_channel_shorts(
            max_results=max_results,
            page_token=page_token,
        )
    except YouTubeServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/schedules", response_model=ScheduleListResponse)
def list_schedules(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return schedule_service.list_schedules(db, status=status)


@router.get("/schedules/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    try:
        return schedule_service.get_schedule(db, schedule_id)
    except ScheduleServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/schedules/{schedule_id}/cancel", status_code=204)
def cancel_schedule(schedule_id: int, db: Session = Depends(get_db)):
    try:
        schedule_service.cancel_schedule(db, schedule_id)
    except ScheduleServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Remove the schedule row from ClipForge (not the YouTube video / local clip)."""
    try:
        schedule_service.delete_schedule(db, schedule_id)
    except ScheduleServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/schedules/{schedule_id}/retry", response_model=ScheduleRead)
def retry_schedule(schedule_id: int, db: Session = Depends(get_db)):
    try:
        return schedule_service.retry_schedule(db, schedule_id)
    except ScheduleServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/clips/{clip_id}/schedule", response_model=ScheduleRead)
def schedule_clip(
    clip_id: int,
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
):
    try:
        return schedule_service.create_schedule(db, clip_id, payload)
    except ScheduleServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
