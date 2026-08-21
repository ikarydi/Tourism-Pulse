from pydantic import BaseModel


class PulseTrendDriversRead(BaseModel):
    positive: list[str]
    negative: list[str]


class PulseTrendAnalysisRead(BaseModel):
    place_id: int
    current_pulse: float
    change_24h: float | None
    change_7d: float | None
    direction: str
    momentum: str
    drivers: PulseTrendDriversRead
