from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class YouTubeStatus(BaseModel):
    configured: bool
    connected: bool
    channel_title: str | None = None
    channel_id: str | None = None
    redirect_uri: str
    can_connect_later: bool = True
    setup_hint: str | None = None


class YouTubeConnectResponse(BaseModel):
    auth_url: str | None = None
    state: str | None = None
    configured: bool
    message: str | None = None


class YouTubeChannelStats(BaseModel):
    channel_id: str | None = None
    title: str | None = None
    thumbnail_url: str | None = None
    subscriber_count: int = 0
    hidden_subscriber_count: bool = False
    view_count: int = 0
    video_count: int = 0
    uploads_playlist_id: str | None = None


class YouTubeShortStats(BaseModel):
    video_id: str
    title: str
    published_at: str | None = None
    duration_seconds: int
    view_count: int = 0
    like_count: int | None = None
    comment_count: int | None = None
    thumbnail_url: str | None = None
    youtube_url: str


class YouTubeShortsListResponse(BaseModel):
    items: list[YouTubeShortStats]
    next_page_token: str | None = None
    total_returned: int = 0
    channel_title: str | None = None
    channel_id: str | None = None


class ScheduleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    privacy_status: str = "private"
    publish_at: datetime | None = None  # interpreted as UTC if naive
    timezone: str = "UTC"

    @field_validator("privacy_status")
    @classmethod
    def validate_privacy(cls, value: str) -> str:
        allowed = {"private", "unlisted", "public"}
        if value not in allowed:
            raise ValueError(f"privacy_status must be one of {sorted(allowed)}")
        return value


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clip_id: int
    title: str
    description: str
    privacy_status: str
    publish_at: datetime | None = None
    timezone: str
    status: str
    youtube_video_id: str | None = None
    youtube_url: str | None = None
    idempotency_key: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    clip_title: str | None = None
    thumbnail_url: str | None = None
    video_id: int | None = None


class ScheduleListResponse(BaseModel):
    items: list[ScheduleRead]
    total: int
