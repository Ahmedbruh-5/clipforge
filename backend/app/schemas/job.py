from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: str
    progress: float
    video_id: int | None = None
    clip_id: int | None = None
    message: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
