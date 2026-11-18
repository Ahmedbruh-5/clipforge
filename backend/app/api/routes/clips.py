from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.clip import ClipCreate, ClipListResponse, ClipRead, ClipUpdate
from app.schemas.job import JobRead
from app.services import clip_service
from app.services.clip_service import ClipServiceError
from app.utils.streaming import range_file_response

router = APIRouter(prefix="/api", tags=["clips"])


@router.post("/clips", response_model=ClipRead)
def create_clip(payload: ClipCreate, db: Session = Depends(get_db)):
    try:
        return clip_service.create_clip(db, payload)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/clips", response_model=ClipListResponse)
def list_clips(
    video_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return clip_service.list_clips(
        db,
        video_id=video_id,
        status=status,
        review_status=review_status,
    )


@router.get("/clips/{clip_id}", response_model=ClipRead)
def get_clip(clip_id: int, db: Session = Depends(get_db)):
    try:
        return clip_service.get_clip(db, clip_id)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put("/clips/{clip_id}", response_model=ClipRead)
def update_clip(clip_id: int, payload: ClipUpdate, db: Session = Depends(get_db)):
    try:
        return clip_service.update_clip(db, clip_id, payload)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/clips/{clip_id}", status_code=204)
def delete_clip(clip_id: int, db: Session = Depends(get_db)):
    try:
        clip_service.delete_clip(db, clip_id)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/clips/{clip_id}/render", response_model=JobRead)
def render_clip(clip_id: int, db: Session = Depends(get_db)):
    try:
        return clip_service.start_render(db, clip_id)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/clips/{clip_id}/stream")
def stream_clip(clip_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        path = clip_service.get_clip_output_path(db, clip_id)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return range_file_response(
        path,
        request,
        media_type="video/mp4",
        filename=path.name,
    )


@router.get("/clips/{clip_id}/thumbnail")
def clip_thumbnail(clip_id: int, db: Session = Depends(get_db)):
    try:
        path = clip_service.get_clip_thumbnail_path(db, clip_id)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return FileResponse(path, media_type="image/jpeg", filename=path.name)


@router.post("/clips/{clip_id}/thumbnail", response_model=ClipRead)
async def upload_clip_thumbnail(
    clip_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        return await clip_service.upload_custom_thumbnail(db, clip_id, file)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/clips/{clip_id}/thumbnail", response_model=ClipRead)
def clear_clip_thumbnail(clip_id: int, db: Session = Depends(get_db)):
    try:
        return clip_service.clear_custom_thumbnail(db, clip_id)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    try:
        return clip_service.get_job(db, job_id)
    except ClipServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# Schedule creation lives in schedules.py as POST /api/clips/{id}/schedule
