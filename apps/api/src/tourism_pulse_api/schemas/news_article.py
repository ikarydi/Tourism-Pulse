from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NewsArticleRead(BaseModel):
    id: int
    place_id: int
    source: str
    url: str
    title: str
    domain: str | None = None
    published_at: datetime | None = None
    tone: float | None = None
    categories: list[str]
    retrieved_at: datetime

    model_config = ConfigDict(from_attributes=True)
