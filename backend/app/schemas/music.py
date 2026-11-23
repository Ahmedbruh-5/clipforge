from pydantic import BaseModel, ConfigDict


class MusicTrackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    source: str  # builtin | user
    id: str
    title: str
    artist: str | None = None
    license: str | None = None
    attribution: str | None = None
    filename: str
    duration: float | None = None
    file_size: int | None = None


class MusicTrackListResponse(BaseModel):
    items: list[MusicTrackRead]
    total: int
