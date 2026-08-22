from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LineageSourceObservationRead(BaseModel):
    id: int
    dataset: str
    retrieved_at: datetime
    source_url: str | None = None
    checksum: str
    schema_version: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LineageSourceRead(BaseModel):
    id: int
    name: str
    category: str
    reliability: Decimal

    model_config = ConfigDict(from_attributes=True)


class LineageQualityResultRead(BaseModel):
    check_name: str
    passed: bool
    severity: str
    detail: str | None = None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SignalLineageRead(BaseModel):
    """"Why is this number what it is" (spec section 15) for one Signal."""

    signal_id: int
    place_id: int
    signal_type: str
    value: Decimal
    unit: str | None = None
    source: str
    observed_at: datetime
    source_observation: LineageSourceObservationRead | None
    source_detail: LineageSourceRead | None
    quality_results: list[LineageQualityResultRead]


class EventLineageRead(BaseModel):
    """"Why is this event what it is" - the same chain-walk, for one Event."""

    event_id: int
    place_id: int
    name: str
    event_type: str
    source: str | None = None
    start_at: datetime
    source_observation: LineageSourceObservationRead | None
    source_detail: LineageSourceRead | None
    quality_results: list[LineageQualityResultRead]
