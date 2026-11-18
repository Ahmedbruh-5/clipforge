from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClipCreate(BaseModel):
    video_id: int
    title: str = "Untitled Clip"
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., gt=0)
    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    crop_x: float = Field(default=0.5, ge=0.0, le=1.0)
    crop_y: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_range(self) -> "ClipCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        if (self.end_time - self.start_time) < 0.5:
            raise ValueError("clip duration must be at least 0.5 seconds")
        return self


class ClipUpdate(BaseModel):
    title: str | None = None
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, gt=0)
    aspect_ratio: str | None = None
    resolution: str | None = None
    crop_x: float | None = Field(default=None, ge=0.0, le=1.0)
    crop_y: float | None = Field(default=None, ge=0.0, le=1.0)
    review_status: str | None = None


class ClipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    title: str
    start_time: float
    end_time: float
    duration: float
    status: str
    review_status: str = "pending"
    output_path: str | None = None
    thumbnail_path: str | None = None
    thumbnail_custom: bool = False
    aspect_ratio: str
    resolution: str
    crop_x: float | None = None
    crop_y: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    stream_url: str | None = None
    thumbnail_url: str | None = None
    video_title: str | None = None


class ClipListResponse(BaseModel):
    items: list[ClipRead]
    total: int
