from datetime import datetime, timedelta
from pathlib import Path

from app.models.clip import Clip
from app.models.video import Video


def _seed_ready_clip(db_session, *, review_status: str, storage: Path) -> Clip:
    source = storage / "originals" / "sample.mp4"
    source.write_bytes(b"\x00" * 64)
    output = storage / "processed" / "clip_out.mp4"
    output.write_bytes(b"\x00" * 128)

    video = Video(
        filename="sample.mp4",
        original_filename="sample.mp4",
        file_path=str(source),
        file_size=64,
        mime_type="video/mp4",
        duration=60.0,
        width=1920,
        height=1080,
        status="ready",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    clip = Clip(
        video_id=video.id,
        title="Test Clip",
        start_time=0,
        end_time=10,
        duration=10,
        status="ready",
        review_status=review_status,
        output_path=str(output),
        aspect_ratio="9:16",
        resolution="1080x1920",
        crop_x=0.5,
        crop_y=0.5,
    )
    db_session.add(clip)
    db_session.commit()
    db_session.refresh(clip)
    return clip


def test_create_clip_validation(client, db_session, tmp_path):
    # Settings storage is under tmp_path/storage from client fixture — create video row
    from app.core.config import get_settings

    storage = Path(get_settings().storage_dir)
    source = storage / "originals" / "v.mp4"
    source.write_bytes(b"\x00" * 32)
    video = Video(
        filename="v.mp4",
        original_filename="v.mp4",
        file_path=str(source),
        file_size=32,
        duration=30.0,
        status="ready",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    bad = client.post(
        "/api/clips",
        json={
            "video_id": video.id,
            "title": "Bad",
            "start_time": 10,
            "end_time": 5,
        },
    )
    assert bad.status_code == 422

    ok = client.post(
        "/api/clips",
        json={
            "video_id": video.id,
            "title": "Good",
            "start_time": 1,
            "end_time": 8,
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
        },
    )
    assert ok.status_code == 200
    data = ok.json()
    assert data["status"] == "draft"
    assert data["review_status"] == "pending"
    assert data["duration"] == 7.0


def test_schedule_requires_approved_clip(client, db_session):
    from app.core.config import get_settings

    storage = Path(get_settings().storage_dir)
    clip = _seed_ready_clip(db_session, review_status="pending", storage=storage)

    response = client.post(
        f"/api/clips/{clip.id}/schedule",
        json={
            "title": "Short",
            "description": "",
            "privacy_status": "private",
            "publish_at": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 400
    assert "approved" in response.json()["detail"].lower()


def test_schedule_rejects_without_youtube(client, db_session):
    from app.core.config import get_settings

    storage = Path(get_settings().storage_dir)
    clip = _seed_ready_clip(db_session, review_status="approved", storage=storage)

    response = client.post(
        f"/api/clips/{clip.id}/schedule",
        json={
            "title": "Short",
            "description": "",
            "privacy_status": "private",
            "timezone": "UTC",
        },
    )
    # OAuth not configured in tests
    assert response.status_code == 400
    assert "oauth" in response.json()["detail"].lower() or "youtube" in response.json()[
        "detail"
    ].lower()


def test_range_stream_for_clip(client, db_session):
    from app.core.config import get_settings

    storage = Path(get_settings().storage_dir)
    clip = _seed_ready_clip(db_session, review_status="approved", storage=storage)

    full = client.get(f"/api/clips/{clip.id}/stream")
    assert full.status_code == 200
    assert full.headers.get("accept-ranges") == "bytes"

    partial = client.get(
        f"/api/clips/{clip.id}/stream",
        headers={"Range": "bytes=0-15"},
    )
    assert partial.status_code == 206
    assert partial.headers.get("content-range", "").startswith("bytes 0-15/")
    assert len(partial.content) == 16
