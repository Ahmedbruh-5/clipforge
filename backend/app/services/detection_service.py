from __future__ import annotations

import logging
import threading
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.engine.detector import generate_candidates
from app.models.candidate import DetectionCandidate
from app.models.clip import Clip
from app.models.job import Job
from app.models.video import Video
from app.schemas.detection import CandidatePromote, CandidateUpdate, DetectionOptions
from app.services.clip_service import _clip_to_dict

logger = logging.getLogger(__name__)
settings = get_settings()


class DetectionServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _candidate_dict(c: DetectionCandidate) -> dict:
    return {
        "id": c.id,
        "video_id": c.video_id,
        "start_time": c.start_time,
        "end_time": c.end_time,
        "duration": c.duration,
        "score": c.score,
        "audio_score": c.audio_score,
        "scene_score": c.scene_score,
        "visual_score": c.visual_score,
        "rank": c.rank,
        "label": c.label,
        "notes": c.notes,
        "created_at": c.created_at,
    }


def list_candidates(db: Session, video_id: int) -> dict:
    video = db.get(Video, video_id)
    if not video:
        raise DetectionServiceError("Video not found", status_code=404)
    rows = db.scalars(
        select(DetectionCandidate)
        .where(DetectionCandidate.video_id == video_id)
        .order_by(DetectionCandidate.rank.asc(), DetectionCandidate.score.desc())
    ).all()
    return {
        "items": [_candidate_dict(r) for r in rows],
        "total": len(rows),
        "disclaimer": (
            "Candidates are ranked signal peaks (audio/scene/motion), "
            "not proof that a moment is interesting."
        ),
    }


def update_candidate(db: Session, candidate_id: int, payload: CandidateUpdate) -> dict:
    candidate = db.get(DetectionCandidate, candidate_id)
    if not candidate:
        raise DetectionServiceError("Candidate not found", status_code=404)

    video = db.get(Video, candidate.video_id)
    data = payload.model_dump(exclude_unset=True)
    start = data.get("start_time", candidate.start_time)
    end = data.get("end_time", candidate.end_time)
    if end <= start:
        raise DetectionServiceError("end_time must be greater than start_time")
    if end - start < 0.5:
        raise DetectionServiceError("candidate duration must be at least 0.5 seconds")
    if video and video.duration is not None and end > video.duration + 0.25:
        raise DetectionServiceError(
            f"end_time exceeds video duration ({video.duration:.2f}s)"
        )

    candidate.start_time = start
    candidate.end_time = end
    candidate.duration = round(end - start, 3)
    if "label" in data and data["label"] is not None:
        candidate.label = data["label"].strip() or candidate.label
    if "notes" in data:
        candidate.notes = data["notes"]

    db.commit()
    db.refresh(candidate)
    return _candidate_dict(candidate)


def delete_candidate(db: Session, candidate_id: int) -> None:
    candidate = db.get(DetectionCandidate, candidate_id)
    if not candidate:
        raise DetectionServiceError("Candidate not found", status_code=404)
    db.delete(candidate)
    db.commit()


def promote_candidate(db: Session, candidate_id: int, payload: CandidatePromote) -> dict:
    candidate = db.get(DetectionCandidate, candidate_id)
    if not candidate:
        raise DetectionServiceError("Candidate not found", status_code=404)

    video = db.get(Video, candidate.video_id)
    if not video:
        raise DetectionServiceError("Source video not found", status_code=404)

    title = (payload.title or "").strip() or f"Candidate #{candidate.rank}"
    clip = Clip(
        video_id=candidate.video_id,
        title=title,
        start_time=candidate.start_time,
        end_time=candidate.end_time,
        duration=round(candidate.end_time - candidate.start_time, 3),
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


def _build_runtime_settings(options: DetectionOptions | None) -> Settings:
    base = get_settings()
    data = base.model_dump()
    if options:
        if options.weight_audio is not None:
            data["detect_weight_audio"] = options.weight_audio
        if options.weight_scene is not None:
            data["detect_weight_scene"] = options.weight_scene
        if options.weight_visual is not None:
            data["detect_weight_visual"] = options.weight_visual
        if options.min_clip_seconds is not None:
            data["detect_min_clip_seconds"] = options.min_clip_seconds
        if options.max_clip_seconds is not None:
            data["detect_max_clip_seconds"] = options.max_clip_seconds
        if options.max_candidates is not None:
            data["detect_max_candidates"] = options.max_candidates
    return Settings(**data)


def _run_detect_job(job_id: int, video_id: int, options: DetectionOptions | None) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        video = db.get(Video, video_id)
        if not job or not video:
            return

        job.status = "running"
        job.progress = 10
        job.message = "Analyzing audio, silence, and scenes"
        db.commit()

        source = Path(video.file_path)
        if not source.exists():
            raise RuntimeError("Source video missing on disk")

        runtime = _build_runtime_settings(options)
        job.progress = 35
        job.message = "Computing candidate scores"
        db.commit()

        candidates = generate_candidates(
            source,
            video.duration,
            settings.temp_dir,
            settings=runtime,
        )

        job.progress = 80
        job.message = "Saving ranked candidates"
        db.commit()

        db.execute(
            delete(DetectionCandidate).where(DetectionCandidate.video_id == video_id)
        )
        for rank, seg in enumerate(candidates, start=1):
            db.add(
                DetectionCandidate(
                    video_id=video_id,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    duration=round(seg.end_time - seg.start_time, 3),
                    score=round(seg.score, 4),
                    audio_score=round(seg.audio_score, 4),
                    scene_score=round(seg.scene_score, 4),
                    visual_score=round(seg.visual_score, 4),
                    rank=rank,
                    label=seg.label,
                    notes=seg.notes,
                )
            )

        job.status = "completed"
        job.progress = 100
        job.message = f"Found {len(candidates)} candidates"
        db.commit()
    except Exception as exc:
        logger.exception("Detection job %s failed", job_id)
        job = db.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.message = "Detection failed"
            db.commit()
    finally:
        db.close()


def start_detection(
    db: Session,
    video_id: int,
    options: DetectionOptions | None = None,
) -> dict:
    video = db.get(Video, video_id)
    if not video:
        raise DetectionServiceError("Video not found", status_code=404)

    job = Job(
        job_type="detect",
        status="queued",
        progress=0,
        video_id=video_id,
        clip_id=None,
        message="Queued for highlight detection",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=_run_detect_job,
        args=(job.id, video_id, options),
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
