from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SignalBase(BaseModel):
    signal_type: str
    value: Decimal
    unit: str | None = None
    observed_at: datetime
    source: str
    source_url: str | None = None


class SignalCreate(SignalBase):
    pass


class SignalRead(SignalBase):
    id: int
    place_id: int

    model_config = ConfigDict(from_attributes=True)
