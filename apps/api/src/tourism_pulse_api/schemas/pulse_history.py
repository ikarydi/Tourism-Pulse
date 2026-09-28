from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PulseSnapshotRead(BaseModel):
    id: int
    place_id: int
    calculated_at: datetime
    pulse: float
    demand: float
    capacity: float
    events: float
    environment: float
    risk: float
    economic: float
    pressure: float | None = None
    confidence_score: float
    confidence_coverage: float
    narrative: str | None = None

    model_config = ConfigDict(from_attributes=True)
