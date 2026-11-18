from __future__ import annotations

import logging
import threading
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from fastapi import UploadFile

from app.engine.processor import process_clip_render, process_thumbnail
from app.models.clip import Clip
from app.models.job import Job
from app.models.video import Video
from app.schemas.clip import ClipCreate, ClipUpdate
from app.utils.ffmpeg import FFmpegError, convert_image_to_jpeg

logger = logging.getLogger(__name__)
settings = get_settings()

RENDER_INVALIDATING_FIELDS = {
    "start_time",
    "end_time",
    "aspect_ratio",
    "resolution",
    "crop_x",
    "crop_y",
}


class ClipServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _clip_to_dict(clip: Clip, video: Video | None = None) -> dict:
    stream_url = None
    if clip.status == "ready" and clip.output_path and Path(clip.output_path).exists():
        stream_url = f"/api/clips/{clip.id}/stream"

    thumbnail_url = None
    if clip.thumbnail_path and Path(clip.thumbnail_path).exists():
        # Cache-bust so browser picks up replaced custom thumbs
        stamp = int(clip.updated_at.timestamp()) if clip.updated_at else 0
        thumbnail_url = f"/api/clips/{clip.id}/thumbnail?v={stamp}"

    return {
        "id": clip.id,
        "video_id": clip.video_id,
        "title": clip.title,
        "start_time": clip.start_time,
        "end_time": clip.end_time,
        "duration": clip.duration,
        "status": clip.status,
        "review_status": getattr(clip, "review_status", None) or "pending",
        "output_path": clip.output_path,
        "thumbnail_path": clip.thumbnail_path,
        "thumbnail_custom": bool(getattr(clip, "thumbnail_custom", False)),
        "aspect_ratio": clip.aspect_ratio,
        "resolution": clip.resolution,
        "crop_x": clip.crop_x,
        "crop_y": clip.crop_y,
        "error_message": clip.error_message,
        "created_at": clip.created_at,
        "updated_at": clip.updated_at,
        "stream_url": stream_url,
        "thumbnail_url": thumbnail_url,
        "video_title": video.original_filename if video else None,
    }


def create_clip(db: Session, payload: ClipCreate) -> dict:
    video = db.get(Video, payload.video_id)
    if not video:
        raise ClipServiceError("Video not found", status_code=404)

    if video.duration is not None and payload.end_time > video.duration + 0.25:
        raise ClipServiceError(
            f"end_time exceeds video duration ({video.duration:.2f}s)"
        )

    clip = Clip(
        video_id=payload.video_id,
        title=payload.title.strip() or "Untitled Clip",
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration=round(payload.end_time - payload.start_time, 3),
        status="draft",
        review_status="pending",
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        crop_x=payload.crop_x,
        crop_y=payload.crop_y,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return _clip_to_dict(clip, video)


def list_clips(
    db: Session,
    video_id: int | None = None,
    *,
    status: str | None = None,
    review_status: str | None = None,
) -> dict:
    query = select(Clip).order_by(Clip.created_at.desc())
    if video_id is not None:
        query = query.where(Clip.video_id == video_id)
    if status:
        query = query.where(Clip.status == status)
    if review_status:
        query = query.where(Clip.review_status == review_status)
    clips = db.scalars(query).all()
    video_ids = {c.video_id for c in clips}
    videos = {
        v.id: v
        for v in db.scalars(select(Video).where(Video.id.in_(video_ids))).all()
    } if video_ids else {}
    items = [_clip_to_dict(c, videos.get(c.video_id)) for c in clips]
    return {"items": items, "total": len(items)}


def get_clip(db: Session, clip_id: int) -> dict:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)
    video = db.get(Video, clip.video_id)
    return _clip_to_dict(clip, video)


def update_clip(db: Session, clip_id: int, payload: ClipUpdate) -> dict:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)

    video = db.get(Video, clip.video_id)
    data = payload.model_dump(exclude_unset=True)

    start = data.get("start_time", clip.start_time)
    end = data.get("end_time", clip.end_time)
    if end <= start:
        raise ClipServiceError("end_time must be greater than start_time")
    if (end - start) < 0.5:
        raise ClipServiceError("clip duration must be at least 0.5 seconds")
    if video and video.duration is not None and end > video.duration + 0.25:
        raise ClipServiceError(
            f"end_time exceeds video duration ({video.duration:.2f}s)"
        )

    if "title" in data and data["title"] is not None:
        clip.title = data["title"].strip() or clip.title
    clip.start_time = start
    clip.end_time = end
    clip.duration = round(end - start, 3)
    if "aspect_ratio" in data and data["aspect_ratio"] is not None:
        clip.aspect_ratio = data["aspect_ratio"]
    if "resolution" in data and data["resolution"] is not None:
        clip.resolution = data["resolution"]
    if "crop_x" in data and data["crop_x"] is not None:
        clip.crop_x = data["crop_x"]
    if "crop_y" in data and data["crop_y"] is not None:
        clip.crop_y = data["crop_y"]
    if "review_status" in data and data["review_status"] is not None:
        allowed = {"pending", "approved", "rejected"}
        if data["review_status"] not in allowed:
            raise ClipServiceError(
                f"review_status must be one of: {', '.join(sorted(allowed))}"
            )
        clip.review_status = data["review_status"]

    if RENDER_INVALIDATING_FIELDS & data.keys():
        if clip.output_path:
            Path(clip.output_path).unlink(missing_ok=True)
        clip.output_path = None
        # Keep custom thumbnails when only timestamps/crop change
        if not getattr(clip, "thumbnail_custom", False):
            if clip.thumbnail_path:
                Path(clip.thumbnail_path).unlink(missing_ok=True)
            clip.thumbnail_path = None
        clip.status = "draft"
        clip.error_message = None

    db.commit()
    db.refresh(clip)
    return _clip_to_dict(clip, video)


def delete_clip(db: Session, clip_id: int) -> None:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)
    if clip.output_path:
        Path(clip.output_path).unlink(missing_ok=True)
    if clip.thumbnail_path:
        Path(clip.thumbnail_path).unlink(missing_ok=True)
    db.delete(clip)
    db.commit()


def get_clip_output_path(db: Session, clip_id: int) -> Path:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)
    if not clip.output_path or not Path(clip.output_path).exists():
        raise ClipServiceError("Rendered clip not available", status_code=404)
    return Path(clip.output_path)


def get_clip_thumbnail_path(db: Session, clip_id: int) -> Path:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)
    if not clip.thumbnail_path or not Path(clip.thumbnail_path).exists():
        raise ClipServiceError("Thumbnail not available", status_code=404)
    return Path(clip.thumbnail_path)


ALLOWED_THUMB_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_THUMB_BYTES = 10 * 1024 * 1024


async def upload_custom_thumbnail(db: Session, clip_id: int, upload: UploadFile) -> dict:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)
    if not upload.filename:
        raise ClipServiceError("Missing filename")

    extension = Path(upload.filename).suffix.lower()
    if extension not in ALLOWED_THUMB_EXTENSIONS:
        raise ClipServiceError(
            f"Unsupported image type '{extension}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_THUMB_EXTENSIONS))}"
        )

    settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = settings.temp_dir / f"thumb_upload_{clip_id}{extension}"
    output_path = settings.thumbnails_dir / f"clip_{clip_id}.jpg"

    size = 0
    try:
        with temp_path.open("wb") as buffer:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_THUMB_BYTES:
                    raise ClipServiceError("Thumbnail exceeds 10 MB limit", status_code=413)
                buffer.write(chunk)
    except ClipServiceError:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise ClipServiceError(f"Failed to save thumbnail: {exc}", status_code=500) from exc
    finally:
        await upload.close()

    try:
        convert_image_to_jpeg(temp_path, output_path)
    except FFmpegError as exc:
        temp_path.unlink(missing_ok=True)
        raise ClipServiceError(str(exc), status_code=400) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if clip.thumbnail_path and Path(clip.thumbnail_path) != output_path:
        Path(clip.thumbnail_path).unlink(missing_ok=True)

    clip.thumbnail_path = str(output_path)
    clip.thumbnail_custom = True
    db.commit()
    db.refresh(clip)
    video = db.get(Video, clip.video_id)
    return _clip_to_dict(clip, video)


def clear_custom_thumbnail(db: Session, clip_id: int) -> dict:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)
    if clip.thumbnail_path:
        Path(clip.thumbnail_path).unlink(missing_ok=True)
    clip.thumbnail_path = None
    clip.thumbnail_custom = False
    db.commit()
    db.refresh(clip)
    video = db.get(Video, clip.video_id)
    return _clip_to_dict(clip, video)


def _run_render_job(job_id: int, clip_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        clip = db.get(Clip, clip_id)
        if not job or not clip:
            return

        video = db.get(Video, clip.video_id)
        if not video:
            job.status = "failed"
            job.error_message = "Source video missing"
            clip.status = "failed"
            clip.error_message = "Source video missing"
            db.commit()
            return

        job.status = "running"
        job.progress = 10
        job.message = "Starting FFmpeg render"
        clip.status = "rendering"
        clip.error_message = None
        db.commit()

        source = Path(video.file_path)
        if not source.exists():
            raise FFmpegError("Source video file not found on disk")

        aspect = clip.aspect_ratio or "9:16"
        resolution = clip.resolution or "1080x1920"
        crop_x = 0.5 if clip.crop_x is None else clip.crop_x
        crop_y = 0.5 if clip.crop_y is None else clip.crop_y

        suffix = "vertical" if aspect in {"9:16", "9/16"} else "clip"
        output_name = (
            f"clip_{clip.id}_{int(clip.start_time)}_{int(clip.end_time)}_{suffix}.mp4"
        )
        output_path = settings.processed_dir / output_name
        thumb_path = settings.thumbnails_dir / f"clip_{clip.id}.jpg"
        settings.processed_dir.mkdir(parents=True, exist_ok=True)
        settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)

        job.progress = 35
        job.message = "Cropping and encoding clip"
        db.commit()

        process_clip_render(
            source,
            output_path,
            clip.start_time,
            clip.end_time,
            source_width=video.width,
            source_height=video.height,
            aspect_ratio=aspect,
            resolution=resolution,
            crop_x=crop_x,
            crop_y=crop_y,
        )

        keep_custom_thumb = bool(getattr(clip, "thumbnail_custom", False)) and bool(
            clip.thumbnail_path and Path(clip.thumbnail_path).exists()
        )

        if keep_custom_thumb:
            job.progress = 90
            job.message = "Keeping custom thumbnail"
            db.commit()
        else:
            job.progress = 75
            job.message = "Generating thumbnail"
            db.commit()

            thumb_ts = clip.start_time + max((clip.end_time - clip.start_time) * 0.2, 0)
            process_thumbnail(
                source,
                thumb_path,
                thumb_ts,
                source_width=video.width,
                source_height=video.height,
                aspect_ratio=aspect,
                resolution=resolution,
                crop_x=crop_x,
                crop_y=crop_y,
            )
            clip.thumbnail_path = str(thumb_path)
            clip.thumbnail_custom = False

        clip.output_path = str(output_path)
        clip.crop_x = crop_x
        clip.crop_y = crop_y
        clip.status = "ready"
        clip.error_message = None
        job.status = "completed"
        job.progress = 100
        job.message = (
            "Clip rendered successfully (custom thumbnail kept)"
            if keep_custom_thumb
            else "Clip rendered successfully"
        )
        db.commit()
    except Exception as exc:
        logger.exception("Render job %s failed", job_id)
        job = db.get(Job, job_id)
        clip = db.get(Clip, clip_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.message = "Render failed"
        if clip:
            clip.status = "failed"
            clip.error_message = str(exc)
        db.commit()
    finally:
        db.close()


def start_render(db: Session, clip_id: int) -> dict:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ClipServiceError("Clip not found", status_code=404)

    video = db.get(Video, clip.video_id)
    if not video:
        raise ClipServiceError("Source video not found", status_code=404)

    job = Job(
        job_type="render",
        status="queued",
        progress=0,
        video_id=clip.video_id,
        clip_id=clip.id,
        message="Queued for rendering",
    )
    clip.status = "rendering"
    clip.error_message = None
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=_run_render_job,
        args=(job.id, clip.id),
        daemon=True,
    )
    thread.start()

    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "video_id": job.video_id,
        "clip_id": job.clip_id,
        "message": job.message,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def get_job(db: Session, job_id: int) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise ClipServiceError("Job not found", status_code=404)
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "video_id": job.video_id,
        "clip_id": job.clip_id,
        "message": job.message,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
