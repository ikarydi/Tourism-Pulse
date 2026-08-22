from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlaceDemographicsRead(BaseModel):
    id: int
    place_id: int
    year: int
    population: int
    source: str
    retrieved_at: datetime

    model_config = ConfigDict(from_attributes=True)
