from pydantic import BaseModel, ConfigDict


class AttractionBase(BaseModel):
    name: str
    category: str
    description: str | None = None


class AttractionCreate(AttractionBase):
    pass


class AttractionRead(AttractionBase):
    id: int
    place_id: int
    latitude: float | None = None
    longitude: float | None = None
    source: str | None = None

    model_config = ConfigDict(from_attributes=True)
