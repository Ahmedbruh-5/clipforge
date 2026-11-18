from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import database
from app.models.clip import Clip
from app.models.job import Job
from app.models.schedule import PublishSchedule
from app.models.video import Video
from app.schemas.schedule import ScheduleCreate
from app.services import youtube_service
from app.services.youtube_service import YouTubeServiceError

logger = logging.getLogger(__name__)


class ScheduleServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).replace(tzinfo=None)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _idempotency_key(clip_id: int, publish_at: datetime | None, title: str) -> str:
    stamp = publish_at.strftime("%Y%m%d%H%M") if publish_at else "immediate"
    raw = f"{clip_id}:{stamp}:{title.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _schedule_dict(schedule: PublishSchedule, clip: Clip | None = None) -> dict:
    thumbnail_url = None
    video_id = None
    clip_title = None
    if clip:
        clip_title = clip.title
        video_id = clip.video_id
        if clip.thumbnail_path and Path(clip.thumbnail_path).exists():
            thumbnail_url = f"/api/clips/{clip.id}/thumbnail"

    return {
        "id": schedule.id,
        "clip_id": schedule.clip_id,
        "title": schedule.title,
        "description": schedule.description,
        "privacy_status": schedule.privacy_status,
        "publish_at": schedule.publish_at,
        "timezone": schedule.timezone,
        "status": schedule.status,
        "youtube_video_id": schedule.youtube_video_id,
        "youtube_url": schedule.youtube_url,
        "idempotency_key": schedule.idempotency_key,
        "error_message": schedule.error_message,
        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
        "clip_title": clip_title,
        "thumbnail_url": thumbnail_url,
        "video_id": video_id,
    }


def list_schedules(db: Session, status: str | None = None) -> dict:
    query = select(PublishSchedule).order_by(PublishSchedule.created_at.desc())
    if status:
        query = query.where(PublishSchedule.status == status)
    rows = db.scalars(query).all()
    clip_ids = {r.clip_id for r in rows}
    clips = {
        c.id: c
        for c in db.scalars(select(Clip).where(Clip.id.in_(clip_ids))).all()
    } if clip_ids else {}
    items = [_schedule_dict(r, clips.get(r.clip_id)) for r in rows]
    return {"items": items, "total": len(items)}


def get_schedule(db: Session, schedule_id: int) -> dict:
    schedule = db.get(PublishSchedule, schedule_id)
    if not schedule:
        raise ScheduleServiceError("Schedule not found", status_code=404)
    clip = db.get(Clip, schedule.clip_id)
    return _schedule_dict(schedule, clip)


def create_schedule(db: Session, clip_id: int, payload: ScheduleCreate) -> dict:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ScheduleServiceError("Clip not found", status_code=404)
    if clip.status != "ready" or not clip.output_path or not Path(clip.output_path).exists():
        raise ScheduleServiceError(
            "Clip must be rendered (status=ready) before scheduling upload",
            status_code=400,
        )
    review = getattr(clip, "review_status", "pending") or "pending"
    if review != "approved":
        raise ScheduleServiceError(
            "Only approved clips can be scheduled. Approve the clip in Clip Review first.",
            status_code=400,
        )

    if not youtube_service.oauth_configured():
        raise ScheduleServiceError(
            "YouTube OAuth is not configured yet. Add credentials in Settings/.env, "
            "then connect your channel.",
            status_code=400,
        )
    if not youtube_service.is_connected():
        raise ScheduleServiceError(
            "YouTube is not connected. Open Settings and click Connect YouTube.",
            status_code=401,
        )

    publish_at = _to_utc(payload.publish_at)
    if publish_at and publish_at <= datetime.utcnow():
        raise ScheduleServiceError("publish_at must be in the future (UTC)", status_code=400)

    key = _idempotency_key(clip_id, publish_at, payload.title)

    existing = db.scalar(
        select(PublishSchedule).where(PublishSchedule.idempotency_key == key)
    )
    if existing and existing.status not in {"failed", "cancelled"}:
        raise ScheduleServiceError(
            "An active schedule with the same clip/time/title already exists",
            status_code=409,
        )

    active = db.scalar(
        select(PublishSchedule).where(
            PublishSchedule.clip_id == clip_id,
            PublishSchedule.status.in_(["queued", "uploading", "scheduled"]),
        )
    )
    if active:
        raise ScheduleServiceError(
            f"Clip already has an active schedule (#{active.id})",
            status_code=409,
        )

    schedule = PublishSchedule(
        clip_id=clip_id,
        title=payload.title.strip(),
        description=payload.description or "",
        privacy_status=payload.privacy_status,
        publish_at=publish_at,
        timezone=payload.timezone or "UTC",
        status="queued",
        idempotency_key=key,
    )
    db.add(schedule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ScheduleServiceError(
            "Duplicate schedule blocked by idempotency check",
            status_code=409,
        ) from exc
    db.refresh(schedule)

    job = Job(
        job_type="upload",
        status="queued",
        progress=0,
        video_id=clip.video_id,
        clip_id=clip.id,
        message=f"Queued YouTube upload for schedule #{schedule.id}",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=_run_upload_job,
        args=(job.id, schedule.id),
        daemon=True,
    )
    thread.start()

    return _schedule_dict(schedule, clip)


def cancel_schedule(db: Session, schedule_id: int) -> None:
    """Soft-cancel an active schedule (keeps the row for history / retry)."""
    schedule = db.get(PublishSchedule, schedule_id)
    if not schedule:
        raise ScheduleServiceError("Schedule not found", status_code=404)
    if schedule.status == "uploading":
        raise ScheduleServiceError("Cannot cancel while uploading", status_code=400)
    if schedule.status in {"cancelled", "published", "failed"}:
        raise ScheduleServiceError(
            f"Schedule is already {schedule.status}; use Delete to remove it from the list",
            status_code=400,
        )
    schedule.status = "cancelled"
    db.commit()


def delete_schedule(db: Session, schedule_id: int) -> None:
    """
    Permanently remove a schedule row from ClipForge.

    Does not delete the YouTube video or the local clip — only the schedule record.
    """
    schedule = db.get(PublishSchedule, schedule_id)
    if not schedule:
        raise ScheduleServiceError("Schedule not found", status_code=404)
    if schedule.status in {"uploading", "queued"}:
        raise ScheduleServiceError(
            "Cannot delete while upload is in progress; wait or cancel first",
            status_code=400,
        )
    db.delete(schedule)
    db.commit()


# Backwards-compatible alias used by older call sites
def soft_cancel_schedule(db: Session, schedule_id: int) -> None:
    cancel_schedule(db, schedule_id)


def retry_schedule(db: Session, schedule_id: int) -> dict:
    schedule = db.get(PublishSchedule, schedule_id)
    if not schedule:
        raise ScheduleServiceError("Schedule not found", status_code=404)
    if schedule.status not in {"failed", "cancelled"}:
        raise ScheduleServiceError("Only failed or cancelled schedules can be retried")

    clip = db.get(Clip, schedule.clip_id)
    if not clip or clip.status != "ready" or not clip.output_path:
        raise ScheduleServiceError("Rendered clip is not available for retry", status_code=400)
    review = getattr(clip, "review_status", "pending") or "pending"
    if review != "approved":
        raise ScheduleServiceError(
            "Only approved clips can be retried for upload",
            status_code=400,
        )

    schedule.status = "queued"
    schedule.error_message = None
    db.commit()

    job = Job(
        job_type="upload",
        status="queued",
        progress=0,
        video_id=clip.video_id,
        clip_id=clip.id,
        message=f"Retrying YouTube upload for schedule #{schedule.id}",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=_run_upload_job,
        args=(job.id, schedule.id),
        daemon=True,
    )
    thread.start()
    return _schedule_dict(schedule, clip)


def _run_upload_job(job_id: int, schedule_id: int) -> None:
    db = database.SessionLocal()
    try:
        job = db.get(Job, job_id)
        schedule = db.get(PublishSchedule, schedule_id)
        if not job or not schedule:
            return

        clip = db.get(Clip, schedule.clip_id)
        if not clip:
            raise YouTubeServiceError("Clip missing")

        job.status = "running"
        job.progress = 15
        job.message = "Uploading to YouTube"
        schedule.status = "uploading"
        schedule.error_message = None
        db.commit()

        result = youtube_service.upload_video_file(
            Path(clip.output_path),
            title=schedule.title,
            description=schedule.description,
            privacy_status=schedule.privacy_status,
            publish_at_utc=schedule.publish_at,
        )

        schedule.youtube_video_id = result["youtube_video_id"]
        schedule.youtube_url = result["youtube_url"]
        if schedule.publish_at:
            schedule.status = "scheduled"
            job.message = "Uploaded as private; YouTube will publish at scheduled time"
        else:
            schedule.status = "published" if schedule.privacy_status == "public" else "scheduled"
            job.message = "Uploaded to YouTube"
        job.status = "completed"
        job.progress = 100
        db.commit()
    except Exception as exc:
        logger.exception("YouTube upload job %s failed", job_id)
        job = db.get(Job, job_id)
        schedule = db.get(PublishSchedule, schedule_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.message = "YouTube upload failed"
        if schedule:
            schedule.status = "failed"
            schedule.error_message = str(exc)
        db.commit()
    finally:
        db.close()


def schedule_stats(db: Session) -> dict[str, int]:
    scheduled = db.scalar(
        select(func.count(PublishSchedule.id)).where(
            PublishSchedule.status.in_(["queued", "uploading", "scheduled"])
        )
    ) or 0
    published = db.scalar(
        select(func.count(PublishSchedule.id)).where(
            PublishSchedule.status == "published"
        )
    ) or 0
    failed = db.scalar(
        select(func.count(PublishSchedule.id)).where(
            PublishSchedule.status == "failed"
        )
    ) or 0
    return {
        "scheduled_uploads": scheduled,
        "published_clips": published,
        "failed_uploads": failed,
    }
