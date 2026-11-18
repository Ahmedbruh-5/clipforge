from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VideoBase(BaseModel):
    original_filename: str
    file_size: int
    mime_type: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    status: str = "ready"


class VideoRead(VideoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    stream_url: str | None = None
    clip_count: int = 0


class VideoListResponse(BaseModel):
    items: list[VideoRead]
    total: int


class DashboardStats(BaseModel):
    total_videos: int = 0
    total_clips: int = 0
    clips_draft: int = 0
    clips_ready: int = 0
    clips_failed: int = 0
    clips_pending_review: int = 0
    clips_approved: int = 0
    scheduled_uploads: int = 0
    published_clips: int = 0
    recent_videos: list[VideoRead] = Field(default_factory=list)
