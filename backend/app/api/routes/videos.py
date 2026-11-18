from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.video import DashboardStats, VideoListResponse, VideoRead
from app.services import video_service
from app.services.video_service import VideoServiceError

router = APIRouter(prefix="/api", tags=["videos"])


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db)):
    return video_service.dashboard_stats(db)


@router.post("/videos/upload", response_model=VideoRead)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        return await video_service.save_upload(db, file)
    except VideoServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/videos", response_model=VideoListResponse)
def list_videos(db: Session = Depends(get_db)):
    return video_service.list_videos(db)


@router.get("/videos/{video_id}", response_model=VideoRead)
def get_video(video_id: int, db: Session = Depends(get_db)):
    try:
        return video_service.get_video(db, video_id)
    except VideoServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: int, db: Session = Depends(get_db)):
    try:
        video_service.delete_video(db, video_id)
    except VideoServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/videos/{video_id}/stream")
def stream_video(video_id: int, db: Session = Depends(get_db)):
    try:
        path = video_service.get_video_path(db, video_id)
    except VideoServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    media_type = "video/mp4"
    suffix = path.suffix.lower()
    if suffix == ".webm":
        media_type = "video/webm"
    elif suffix == ".mov":
        media_type = "video/quicktime"
    elif suffix == ".mkv":
        media_type = "video/x-matroska"

    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        headers={"Accept-Ranges": "bytes"},
    )


