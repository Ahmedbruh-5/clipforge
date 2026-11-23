from pathlib import Path

from app.models.video import Video


def _seed_video(db_session, storage: Path) -> Video:
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
    return video


def test_list_builtin_music_tracks(client):
    response = client.get("/api/music/tracks")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    builtin = [t for t in data["items"] if t["source"] == "builtin"]
    assert builtin
    assert all(t["key"].startswith("builtin:") for t in builtin)
    assert all(t["license"] for t in builtin)


def test_upload_and_delete_user_music(client, tmp_path):
    # Minimal valid-ish wav header + silence payload is enough for storage;
    # metadata probe may fail and duration stays null.
    audio = tmp_path / "loop.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 60)

    with audio.open("rb") as handle:
        uploaded = client.post(
            "/api/music/upload",
            files={"file": ("my_loop.wav", handle, "audio/wav")},
        )
    assert uploaded.status_code == 200
    track = uploaded.json()
    assert track["source"] == "user"
    assert track["key"].startswith("user:")
    filename = track["filename"]

    listed = client.get("/api/music/tracks").json()
    assert any(t["key"] == track["key"] for t in listed["items"])

    deleted = client.delete(f"/api/music/user/{filename}")
    assert deleted.status_code == 204

    listed_after = client.get("/api/music/tracks").json()
    assert not any(t["filename"] == filename for t in listed_after["items"])


def test_reject_unsupported_music_type(client, tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("nope")
    with bad.open("rb") as handle:
        response = client.post(
            "/api/music/upload",
            files={"file": ("x.txt", handle, "text/plain")},
        )
    assert response.status_code == 400


def test_create_clip_mute_and_music(client, db_session):
    from app.core.config import get_settings

    storage = Path(get_settings().storage_dir)
    video = _seed_video(db_session, storage)

    muted = client.post(
        "/api/clips",
        json={
            "video_id": video.id,
            "title": "Muted",
            "start_time": 1,
            "end_time": 8,
            "audio_mode": "mute",
        },
    )
    assert muted.status_code == 200
    assert muted.json()["audio_mode"] == "mute"
    assert muted.json()["music_track_key"] is None

    tracks = client.get("/api/music/tracks").json()["items"]
    builtin = next(t for t in tracks if t["source"] == "builtin")

    music = client.post(
        "/api/clips",
        json={
            "video_id": video.id,
            "title": "With music",
            "start_time": 2,
            "end_time": 10,
            "audio_mode": "music",
            "music_track_key": builtin["key"],
            "music_volume": 0.8,
        },
    )
    assert music.status_code == 200
    body = music.json()
    assert body["audio_mode"] == "music"
    assert body["music_track_key"] == builtin["key"]
    assert body["music_volume"] == 0.8


def test_create_clip_music_requires_track(client, db_session):
    from app.core.config import get_settings

    storage = Path(get_settings().storage_dir)
    video = _seed_video(db_session, storage)

    missing = client.post(
        "/api/clips",
        json={
            "video_id": video.id,
            "title": "No track",
            "start_time": 1,
            "end_time": 5,
            "audio_mode": "music",
        },
    )
    assert missing.status_code == 422

    bad_key = client.post(
        "/api/clips",
        json={
            "video_id": video.id,
            "title": "Bad track",
            "start_time": 1,
            "end_time": 5,
            "audio_mode": "music",
            "music_track_key": "builtin:does_not_exist",
        },
    )
    assert bad_key.status_code == 404
