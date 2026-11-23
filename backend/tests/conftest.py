from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend/ is on sys.path when pytest is run from repo root or backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    storage = tmp_path / "storage"
    for name in ("originals", "processed", "thumbnails", "temp", "secrets", "music/user"):
        (storage / name).mkdir(parents=True)

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")

    from app.core.config import get_settings

    get_settings.cache_clear()
    fresh = get_settings()

    from app.core import database as database_module

    database_module.configure_engine()
    database_module.init_db()

    # Rebind module-level settings captured at import time
    import app.api.routes.schedules as schedules_routes
    import app.main as main_module
    import app.services.clip_service as clip_service
    import app.services.detection_service as detection_service
    import app.services.music_service as music_service
    import app.services.video_service as video_service

    monkeypatch.setattr(main_module, "settings", fresh)
    monkeypatch.setattr(video_service, "settings", fresh)
    monkeypatch.setattr(clip_service, "settings", fresh)
    monkeypatch.setattr(detection_service, "settings", fresh)
    monkeypatch.setattr(music_service, "settings", fresh)
    monkeypatch.setattr(schedules_routes, "settings", fresh)

    from app.main import app
    from app.services.job_recovery import shutdown_scheduler

    with TestClient(app) as test_client:
        yield test_client

    shutdown_scheduler()
    get_settings.cache_clear()


@pytest.fixture()
def db_session(client):
    from app.core import database

    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()
