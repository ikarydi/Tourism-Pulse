from pydantic import BaseModel, ConfigDict


class PlaceBase(BaseModel):
    name: str
    place_type: str


class PlaceCreate(PlaceBase):
    pass


class PlaceRead(PlaceBase):
    id: int
    destination_id: int
    latitude: float | None = None
    longitude: float | None = None

    model_config = ConfigDict(from_attributes=True)
