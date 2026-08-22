from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoItemRead(BaseModel):
    id: int
    place_id: int
    source: str
    video_id: str
    title: str
    channel: str | None = None
    published_at: datetime | None = None
    categories: list[str]
    retrieved_at: datetime

    model_config = ConfigDict(from_attributes=True)
