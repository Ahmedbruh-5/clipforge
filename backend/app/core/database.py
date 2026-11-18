from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

db_url = settings.resolved_database_url
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


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
    if "clips" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("clips")}
    with engine.begin() as conn:
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


def init_db() -> None:
    # Import models so metadata is registered before create_all
    from app.models import candidate, clip, job, schedule, video  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
