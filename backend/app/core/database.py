"""SQLAlchemy engine/session setup.

SQLite is the default local-first database. Set DATABASE_URL to a PostgreSQL
URL later (e.g. postgresql+psycopg://user:pass@host/db) without rewriting
models — keep this module as the single connection boundary.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine: Engine
SessionLocal: sessionmaker[Session]
db_url: str


class Base(DeclarativeBase):
    pass


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def configure_engine(url: str | None = None) -> Engine:
    """(Re)create the global engine. Used at import and by tests."""
    global engine, SessionLocal, db_url
    settings = get_settings()
    db_url = url or settings.resolved_database_url
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    # pool_pre_ping helps Postgres reconnect after idle drops; harmless for SQLite
    engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
    if db_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine


configure_engine()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_columns() -> None:
    """Add newly introduced columns on existing SQLite databases."""
    if not db_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.begin() as conn:
        if "clips" in tables:
            existing = {col["name"] for col in inspector.get_columns("clips")}
            if "review_status" not in existing:
                conn.execute(
                    text(
                        "ALTER TABLE clips ADD COLUMN review_status VARCHAR(32) "
                        "NOT NULL DEFAULT 'pending'"
                    )
                )
            if "thumbnail_custom" not in existing:
                conn.execute(
                    text(
                        "ALTER TABLE clips ADD COLUMN thumbnail_custom BOOLEAN "
                        "NOT NULL DEFAULT 0"
                    )
                )
            if "audio_mode" not in existing:
                conn.execute(
                    text(
                        "ALTER TABLE clips ADD COLUMN audio_mode VARCHAR(16) "
                        "NOT NULL DEFAULT 'original'"
                    )
                )
            if "music_track_key" not in existing:
                conn.execute(
                    text("ALTER TABLE clips ADD COLUMN music_track_key VARCHAR(255)")
                )
            if "music_volume" not in existing:
                conn.execute(
                    text(
                        "ALTER TABLE clips ADD COLUMN music_volume FLOAT "
                        "NOT NULL DEFAULT 1.0"
                    )
                )
        if "detection_candidates" in tables:
            cand_cols = {
                col["name"] for col in inspector.get_columns("detection_candidates")
            }
            if "promoted" not in cand_cols:
                conn.execute(
                    text(
                        "ALTER TABLE detection_candidates ADD COLUMN promoted "
                        "BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if "promoted_clip_id" not in cand_cols:
                conn.execute(
                    text(
                        "ALTER TABLE detection_candidates ADD COLUMN "
                        "promoted_clip_id INTEGER"
                    )
                )


def init_db() -> None:
    # Import models so metadata is registered before create_all
    from app.models import candidate, clip, job, schedule, video  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
