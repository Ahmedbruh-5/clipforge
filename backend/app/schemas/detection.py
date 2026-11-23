from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DetectionOptions(BaseModel):
    weight_audio: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_scene: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_visual: float | None = Field(default=None, ge=0.0, le=1.0)
    min_clip_seconds: float | None = Field(default=None, gt=0.5)
    max_clip_seconds: float | None = Field(default=None, gt=1.0)
    max_candidates: int | None = Field(default=None, ge=1, le=100)


class CandidateUpdate(BaseModel):
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, gt=0)
    label: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "CandidateUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be greater than start_time")
            if self.end_time - self.start_time < 0.5:
                raise ValueError("candidate duration must be at least 0.5 seconds")
        return self


class CandidatePromote(BaseModel):
    title: str | None = None
    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    crop_x: float = Field(default=0.5, ge=0.0, le=1.0)
    crop_y: float = Field(default=0.5, ge=0.0, le=1.0)
    audio_mode: str = "original"
    music_track_key: str | None = None
    music_volume: float = Field(default=1.0, ge=0.0, le=2.0)


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    start_time: float
    end_time: float
    duration: float
    score: float
    audio_score: float
    scene_score: float
    visual_score: float
    rank: int
    label: str
    notes: str | None = None
    promoted: bool = False
    promoted_clip_id: int | None = None
    created_at: datetime


class CandidateListResponse(BaseModel):
    items: list[CandidateRead]
    total: int
    disclaimer: str = (
        "Candidates are ranked signal peaks (audio/scene/motion), "
        "not proof that a moment is interesting."
    )
