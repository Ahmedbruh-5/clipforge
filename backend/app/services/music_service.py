from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.utils.ffmpeg import extract_metadata
from app.utils.files import ensure_storage_dirs, sanitize_filename, unique_storage_name

logger = logging.getLogger(__name__)
settings = get_settings()

_SAFE_USER_NAME = re.compile(r"^[A-Za-z0-9._\- ]+$")


class MusicServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def ensure_music_dirs() -> None:
    ensure_storage_dirs(settings.music_user_dir)
    settings.music_builtin_dir.mkdir(parents=True, exist_ok=True)


def _track_dict(
    *,
    key: str,
    source: str,
    track_id: str,
    title: str,
    filename: str,
    path: Path,
    artist: str | None = None,
    license_name: str | None = None,
    attribution: str | None = None,
    duration: float | None = None,
) -> dict:
    size = path.stat().st_size if path.exists() else None
    return {
        "key": key,
        "source": source,
        "id": track_id,
        "title": title,
        "artist": artist,
        "license": license_name,
        "attribution": attribution,
        "filename": filename,
        "duration": duration,
        "file_size": size,
    }


def _load_builtin_catalog() -> list[dict]:
    catalog_path = settings.music_builtin_dir / "catalog.json"
    if not catalog_path.exists():
        return []
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read builtin music catalog: %s", exc)
        return []
    tracks = data.get("tracks") if isinstance(data, dict) else data
    if not isinstance(tracks, list):
        return []
    return [t for t in tracks if isinstance(t, dict)]


def list_tracks() -> dict:
    ensure_music_dirs()
    items: list[dict] = []

    for entry in _load_builtin_catalog():
        track_id = str(entry.get("id") or "").strip()
        filename = str(entry.get("filename") or "").strip()
        if not track_id or not filename:
            continue
        path = settings.music_builtin_dir / Path(filename).name
        if not path.exists():
            continue
        items.append(
            _track_dict(
                key=f"builtin:{track_id}",
                source="builtin",
                track_id=track_id,
                title=str(entry.get("title") or track_id),
                filename=path.name,
                path=path,
                artist=entry.get("artist"),
                license_name=entry.get("license"),
                attribution=entry.get("attribution"),
                duration=(
                    float(entry["duration"])
                    if entry.get("duration") is not None
                    else None
                ),
            )
        )

    for path in sorted(settings.music_user_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in settings.allowed_music_extension_set:
            continue
        duration = None
        try:
            meta = extract_metadata(path)
            duration = meta.duration
        except Exception:
            pass
        items.append(
            _track_dict(
                key=f"user:{path.name}",
                source="user",
                track_id=path.name,
                title=path.stem.replace("_", " "),
                filename=path.name,
                path=path,
                artist=None,
                license_name="user_upload",
                attribution="Uploaded by you — ensure you have rights to use it.",
                duration=duration,
            )
        )

    return {"items": items, "total": len(items)}


def resolve_track_path(track_key: str | None) -> Path | None:
    """Resolve builtin:<id> or user:<filename> to a local file path."""
    if not track_key:
        return None
    key = track_key.strip()
    if key.startswith("builtin:"):
        track_id = key.removeprefix("builtin:").strip()
        for entry in _load_builtin_catalog():
            if str(entry.get("id") or "").strip() == track_id:
                filename = str(entry.get("filename") or "").strip()
                if not filename:
                    return None
                path = settings.music_builtin_dir / Path(filename).name
                return path if path.exists() else None
        return None
    if key.startswith("user:"):
        filename = Path(key.removeprefix("user:")).name
        if not filename or not _SAFE_USER_NAME.match(filename):
            return None
        path = settings.music_user_dir / filename
        return path if path.is_file() else None
    return None


async def upload_track(upload: UploadFile) -> dict:
    ensure_music_dirs()
    if not upload.filename:
        raise MusicServiceError("Missing filename")

    extension = Path(upload.filename).suffix.lower()
    if extension not in settings.allowed_music_extension_set:
        raise MusicServiceError(
            f"Unsupported music type '{extension}'. Allowed: "
            f"{', '.join(sorted(settings.allowed_music_extension_set))}"
        )

    stored_name = unique_storage_name(sanitize_filename(upload.filename))
    # Keep extension from original
    if not Path(stored_name).suffix:
        stored_name = f"{stored_name}{extension}"
    destination = settings.music_user_dir / stored_name

    size = 0
    chunk_size = 1024 * 256
    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_music_upload_bytes:
                    raise MusicServiceError(
                        f"Music file exceeds "
                        f"{settings.max_music_upload_bytes // (1024 * 1024)} MB limit"
                    )
                buffer.write(chunk)
    except MusicServiceError:
        destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise MusicServiceError(f"Failed to save music file: {exc}") from exc

    duration = None
    try:
        duration = extract_metadata(destination).duration
    except Exception:
        pass

    return _track_dict(
        key=f"user:{destination.name}",
        source="user",
        track_id=destination.name,
        title=Path(upload.filename).stem.replace("_", " "),
        filename=destination.name,
        path=destination,
        artist=None,
        license_name="user_upload",
        attribution="Uploaded by you — ensure you have rights to use it.",
        duration=duration,
    )


def delete_user_track(filename: str) -> None:
    ensure_music_dirs()
    name = Path(filename).name
    if not name or not _SAFE_USER_NAME.match(name):
        raise MusicServiceError("Invalid filename", status_code=400)
    path = settings.music_user_dir / name
    if not path.is_file():
        raise MusicServiceError("Track not found", status_code=404)
    path.unlink(missing_ok=True)
