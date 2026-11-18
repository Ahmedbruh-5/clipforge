from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# clipforge/backend/app/core/config.py -> clipforge/
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ClipForge"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000

    # Default: local SQLite. Override with DATABASE_URL for PostgreSQL later, e.g.
    # postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'database' / 'clipforge.db'}"
    storage_dir: str = str(PROJECT_ROOT / "storage")
    max_upload_bytes: int = 2 * 1024 * 1024 * 1024  # 2GB
    allowed_extensions: str = ".mp4,.mov,.mkv,.webm"

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_url: str = "http://127.0.0.1:5173"

    # Detection defaults
    detect_weight_audio: float = 0.50
    detect_weight_scene: float = 0.20
    detect_weight_visual: float = 0.30
    detect_window_seconds: float = 1.0
    detect_min_clip_seconds: float = 8.0
    detect_max_clip_seconds: float = 45.0
    detect_merge_gap_seconds: float = 2.5
    detect_max_candidates: int = 20
    detect_silence_noise_db: float = -35.0
    detect_silence_min_duration: float = 0.6
    detect_scene_threshold: float = 0.35

    # YouTube OAuth — leave empty to connect later
    google_client_id: str = ""
    google_client_secret: str = ""
    youtube_redirect_uri: str = "http://127.0.0.1:8000/api/youtube/callback"
    youtube_token_path: str = str(PROJECT_ROOT / "storage" / "secrets" / "youtube_token.json")

    def model_post_init(self, __context: object) -> None:
        # Avoid invisible whitespace from pasted Cloud Console values
        object.__setattr__(self, "google_client_id", self.google_client_id.strip())
        object.__setattr__(self, "google_client_secret", self.google_client_secret.strip())
        object.__setattr__(self, "youtube_redirect_uri", self.youtube_redirect_uri.strip())

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///"):
            raw = url.removeprefix("sqlite:///")
            if raw.startswith("/") or (len(raw) > 2 and raw[1] == ":"):
                return url
            absolute = (PROJECT_ROOT / raw).resolve()
            return f"sqlite:///{absolute}"
        return url

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def originals_dir(self) -> Path:
        return self.storage_path / "originals"

    @property
    def processed_dir(self) -> Path:
        return self.storage_path / "processed"

    @property
    def thumbnails_dir(self) -> Path:
        return self.storage_path / "thumbnails"

    @property
    def temp_dir(self) -> Path:
        return self.storage_path / "temp"

    @property
    def secrets_dir(self) -> Path:
        return self.storage_path / "secrets"

    @property
    def resolved_youtube_token_path(self) -> Path:
        path = Path(self.youtube_token_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def youtube_oauth_configured(self) -> bool:
        return bool(self.google_client_id.strip() and self.google_client_secret.strip())

    @property
    def allowed_extension_set(self) -> set[str]:
        return {
            ext.strip().lower()
            for ext in self.allowed_extensions.split(",")
            if ext.strip()
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
