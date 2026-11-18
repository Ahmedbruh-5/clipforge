"""Recover jobs interrupted by process restarts; APScheduler periodic sweep."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core import database
from app.models.clip import Clip
from app.models.job import Job
from app.models.schedule import PublishSchedule

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

STALE_RUNNING_MINUTES = 90


def recover_interrupted_work(*, reason: str = "Interrupted by server restart") -> dict[str, int]:
    """
    Mark in-flight jobs/clips/schedules as failed so the UI can retry.

    Daemon threads die with the process; without this, rows stay stuck in
    running/queued/rendering/uploading forever.
    """
    db = database.SessionLocal()
    counts = {"jobs": 0, "clips": 0, "schedules": 0}
    try:
        jobs = db.scalars(
            select(Job).where(Job.status.in_(["queued", "running"]))
        ).all()
        for job in jobs:
            job.status = "failed"
            job.error_message = reason
            job.message = reason
            counts["jobs"] += 1

        clips = db.scalars(select(Clip).where(Clip.status == "rendering")).all()
        for clip in clips:
            clip.status = "failed"
            clip.error_message = reason
            counts["clips"] += 1

        schedules = db.scalars(
            select(PublishSchedule).where(
                PublishSchedule.status.in_(["queued", "uploading"])
            )
        ).all()
        for schedule in schedules:
            schedule.status = "failed"
            schedule.error_message = reason
            counts["schedules"] += 1

        if any(counts.values()):
            db.commit()
            logger.warning(
                "Recovered interrupted work: jobs=%s clips=%s schedules=%s (%s)",
                counts["jobs"],
                counts["clips"],
                counts["schedules"],
                reason,
            )
        else:
            db.rollback()
    except Exception:
        logger.exception("Job recovery failed")
        db.rollback()
    finally:
        db.close()
    return counts


def sweep_stale_running_jobs() -> dict[str, int]:
    """Fail jobs that have been 'running' longer than STALE_RUNNING_MINUTES."""
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_RUNNING_MINUTES)
    db = database.SessionLocal()
    counts = {"jobs": 0, "clips": 0}
    try:
        jobs = db.scalars(
            select(Job).where(Job.status == "running", Job.updated_at < cutoff)
        ).all()
        for job in jobs:
            job.status = "failed"
            job.error_message = (
                f"Marked failed after {STALE_RUNNING_MINUTES}m with no progress"
            )
            job.message = "Stale running job"
            counts["jobs"] += 1
            if job.clip_id and job.job_type == "render":
                clip = db.get(Clip, job.clip_id)
                if clip and clip.status == "rendering":
                    clip.status = "failed"
                    clip.error_message = job.error_message
                    counts["clips"] += 1
        if counts["jobs"]:
            db.commit()
            logger.warning("Swept stale jobs: %s", counts)
        else:
            db.rollback()
    except Exception:
        logger.exception("Stale job sweep failed")
        db.rollback()
    finally:
        db.close()
    return counts


def start_scheduler() -> BackgroundScheduler:
    """Start APScheduler for periodic recovery sweeps (idempotent)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        sweep_stale_running_jobs,
        trigger="interval",
        minutes=15,
        id="sweep_stale_jobs",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("APScheduler started (stale job sweep every 15m)")
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    _scheduler = None
