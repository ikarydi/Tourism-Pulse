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
    confidence_score: float
    confidence_coverage: float

    model_config = ConfigDict(from_attributes=True)
