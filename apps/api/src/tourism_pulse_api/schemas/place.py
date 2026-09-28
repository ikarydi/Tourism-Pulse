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


class PlaceSummaryRead(BaseModel):
    """One row of GET /places: every place with what lists and maps need."""

    id: int
    name: str
    place_type: str
    destination_id: int
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    nuts_code: str | None = None
    nuts3_code: str | None = None
    urau_code: str | None = None
