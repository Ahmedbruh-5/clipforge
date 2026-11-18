from __future__ import annotations

import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.engine.processor import read_media_metadata
from app.models.candidate import DetectionCandidate
from app.models.clip import Clip
from app.models.schedule import PublishSchedule
from app.models.video import Video
from app.services import schedule_service
from app.utils.ffmpeg import FFmpegError
from app.utils.files import ensure_storage_dirs, unique_storage_name

logger = logging.getLogger(__name__)
settings = get_settings()


class VideoServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _video_to_dict(video: Video, clip_count: int = 0) -> dict:
    return {
        "id": video.id,
        "filename": video.filename,
        "original_filename": video.original_filename,
        "file_size": video.file_size,
        "mime_type": video.mime_type,
        "duration": video.duration,
        "width": video.width,
        "height": video.height,
        "fps": video.fps,
        "codec": video.codec,
        "status": video.status,
        "error_message": video.error_message,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
        "stream_url": f"/api/videos/{video.id}/stream",
        "clip_count": clip_count,
    }


def ensure_dirs() -> None:
    ensure_storage_dirs(
        settings.originals_dir,
        settings.processed_dir,
        settings.thumbnails_dir,
        settings.temp_dir,
    )


async def save_upload(db: Session, upload: UploadFile) -> dict:
    ensure_dirs()

    if not upload.filename:
        raise VideoServiceError("Missing filename")

    extension = Path(upload.filename).suffix.lower()
    if extension not in settings.allowed_extension_set:
        raise VideoServiceError(
            f"Unsupported file type '{extension}'. Allowed: "
            f"{', '.join(sorted(settings.allowed_extension_set))}"
        )

    stored_name = unique_storage_name(upload.filename)
    destination = settings.originals_dir / stored_name

    size = 0
    chunk_size = 1024 * 1024
    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    buffer.close()
                    destination.unlink(missing_ok=True)
                    raise VideoServiceError(
                        f"File exceeds upload limit of "
                        f"{settings.max_upload_bytes // (1024 * 1024)} MB",
                        status_code=413,
                    )
                buffer.write(chunk)
    except VideoServiceError:
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise VideoServiceError(f"Failed to save upload: {exc}", status_code=500) from exc
    finally:
        await upload.close()

    video = Video(
        filename=stored_name,
        original_filename=upload.filename,
        file_path=str(destination),
        file_size=size,
        mime_type=upload.content_type,
        status="processing",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    try:
        meta = read_media_metadata(destination)
        video.duration = meta.duration
        video.width = meta.width
        video.height = meta.height
        video.fps = meta.fps
        video.codec = meta.codec
        video.status = "ready"
        video.error_message = None
    except FFmpegError as exc:
        logger.warning("Metadata extraction failed for video %s: %s", video.id, exc)
        video.status = "ready"
        video.error_message = f"Metadata extraction warning: {exc}"
    except Exception as exc:
        logger.exception("Unexpected metadata error for video %s", video.id)
        video.status = "failed"
        video.error_message = str(exc)

    db.commit()
    db.refresh(video)
    return _video_to_dict(video, clip_count=0)


def list_videos(db: Session) -> dict:
    videos = db.scalars(select(Video).order_by(Video.created_at.desc())).all()
    counts = dict(
        db.execute(
            select(Clip.video_id, func.count(Clip.id)).group_by(Clip.video_id)
        ).all()
    )
    items = [_video_to_dict(v, clip_count=counts.get(v.id, 0)) for v in videos]
    return {"items": items, "total": len(items)}


def get_video(db: Session, video_id: int) -> dict:
    video = db.get(Video, video_id)
    if not video:
        raise VideoServiceError("Video not found", status_code=404)
    clip_count = db.scalar(
        select(func.count(Clip.id)).where(Clip.video_id == video_id)
    ) or 0
    return _video_to_dict(video, clip_count=clip_count)


def get_video_path(db: Session, video_id: int) -> Path:
    video = db.get(Video, video_id)
    if not video:
        raise VideoServiceError("Video not found", status_code=404)
    path = Path(video.file_path)
    if not path.exists():
        raise VideoServiceError("Video file missing on disk", status_code=404)
    return path


def delete_video(db: Session, video_id: int) -> None:
    video = db.get(Video, video_id)
    if not video:
        raise VideoServiceError("Video not found", status_code=404)

    clips = db.scalars(select(Clip).where(Clip.video_id == video_id)).all()
    for clip in clips:
        schedules = db.scalars(
            select(PublishSchedule).where(PublishSchedule.clip_id == clip.id)
        ).all()
        for schedule in schedules:
            db.delete(schedule)
        if clip.output_path:
            Path(clip.output_path).unlink(missing_ok=True)
        if clip.thumbnail_path:
            Path(clip.thumbnail_path).unlink(missing_ok=True)
        db.delete(clip)

    candidates = db.scalars(
        select(DetectionCandidate).where(DetectionCandidate.video_id == video_id)
    ).all()
    for candidate in candidates:
        db.delete(candidate)

    Path(video.file_path).unlink(missing_ok=True)
    db.delete(video)
    db.commit()


def dashboard_stats(db: Session) -> dict:
    total_videos = db.scalar(select(func.count(Video.id))) or 0
    total_clips = db.scalar(select(func.count(Clip.id))) or 0
    clips_draft = db.scalar(
        select(func.count(Clip.id)).where(Clip.status == "draft")
    ) or 0
    clips_ready = db.scalar(
        select(func.count(Clip.id)).where(Clip.status == "ready")
    ) or 0
    clips_failed = db.scalar(
        select(func.count(Clip.id)).where(Clip.status == "failed")
    ) or 0
    clips_pending_review = db.scalar(
        select(func.count(Clip.id)).where(Clip.review_status == "pending")
    ) or 0
    clips_approved = db.scalar(
        select(func.count(Clip.id)).where(Clip.review_status == "approved")
    ) or 0

    recent = db.scalars(select(Video).order_by(Video.created_at.desc()).limit(5)).all()
    counts = dict(
        db.execute(
            select(Clip.video_id, func.count(Clip.id)).group_by(Clip.video_id)
        ).all()
    )

    publish_stats = schedule_service.schedule_stats(db)

    return {
        "total_videos": total_videos,
        "total_clips": total_clips,
        "clips_draft": clips_draft,
        "clips_ready": clips_ready,
        "clips_failed": clips_failed,
        "clips_pending_review": clips_pending_review,
        "clips_approved": clips_approved,
        "scheduled_uploads": publish_stats["scheduled_uploads"],
        "published_clips": publish_stats["published_clips"],
        "recent_videos": [_video_to_dict(v, counts.get(v.id, 0)) for v in recent],
    }
