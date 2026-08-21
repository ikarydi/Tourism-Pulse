from pydantic import BaseModel


class PulseAnomalyRead(BaseModel):
    place_id: int
    detected: bool
    severity: str
    change: float | None
    message: str
    drivers: list[str]
