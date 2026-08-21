from pydantic import BaseModel, ConfigDict


class DestinationBase(BaseModel):
    country_code: str
    name: str


class DestinationCreate(DestinationBase):
    pass


class DestinationRead(DestinationBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
