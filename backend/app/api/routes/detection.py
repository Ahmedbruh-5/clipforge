from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.clip import ClipRead
from app.schemas.detection import (
    CandidateListResponse,
    CandidatePromote,
    CandidateRead,
    CandidateUpdate,
    DetectionOptions,
)
from app.schemas.job import JobRead
from app.services import detection_service
from app.services.detection_service import DetectionServiceError

router = APIRouter(prefix="/api", tags=["detection"])


@router.post("/videos/{video_id}/detect", response_model=JobRead)
def detect_highlights(
    video_id: int,
    options: DetectionOptions | None = None,
    db: Session = Depends(get_db),
):
    try:
        return detection_service.start_detection(db, video_id, options)
    except DetectionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/videos/{video_id}/candidates", response_model=CandidateListResponse)
def get_candidates(video_id: int, db: Session = Depends(get_db)):
    try:
        return detection_service.list_candidates(db, video_id)
    except DetectionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put("/candidates/{candidate_id}", response_model=CandidateRead)
def update_candidate(
    candidate_id: int,
    payload: CandidateUpdate,
    db: Session = Depends(get_db),
):
    try:
        return detection_service.update_candidate(db, candidate_id, payload)
    except DetectionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/candidates/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    try:
        detection_service.delete_candidate(db, candidate_id)
    except DetectionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/candidates/{candidate_id}/promote", response_model=ClipRead)
def promote_candidate(
    candidate_id: int,
    payload: CandidatePromote | None = None,
    db: Session = Depends(get_db),
):
    try:
        return detection_service.promote_candidate(
            db, candidate_id, payload or CandidatePromote()
        )
    except DetectionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
