from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventBase(BaseModel):
    name: str
    event_type: str
    description: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    source_url: str | None = None
    source: str | None = None
    external_id: str | None = None


class EventCreate(EventBase):
    pass


class EventRead(EventBase):
    id: int
    place_id: int

    model_config = ConfigDict(from_attributes=True)
