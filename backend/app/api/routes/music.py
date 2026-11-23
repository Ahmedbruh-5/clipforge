from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.schemas.music import MusicTrackListResponse, MusicTrackRead
from app.services import music_service
from app.services.music_service import MusicServiceError

router = APIRouter(prefix="/api/music", tags=["music"])

_MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
}


@router.get("/tracks", response_model=MusicTrackListResponse)
def list_music_tracks():
    return music_service.list_tracks()


@router.get("/file")
def stream_music_file(key: str = Query(..., min_length=3)):
    path = music_service.resolve_track_path(key)
    if path is None:
        raise HTTPException(status_code=404, detail="Music track not found")
    media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.post("/upload", response_model=MusicTrackRead)
async def upload_music_track(file: UploadFile = File(...)):
    try:
        return await music_service.upload_track(file)
    except MusicServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/user/{filename}", status_code=204)
def delete_music_track(filename: str):
    try:
        music_service.delete_user_track(filename)
    except MusicServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
