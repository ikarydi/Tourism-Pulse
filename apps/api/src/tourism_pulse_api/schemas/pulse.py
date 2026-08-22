from pydantic import BaseModel


class PulseDimensionsRead(BaseModel):
    demand: float
    capacity: float
    events: float
    environment: float
    risk: float
    economic: float


class PulseConfidenceRead(BaseModel):
    score: float
    coverage: float


class PulseTrendRead(BaseModel):
    change: float
    direction: str


class PulseInterpretationRead(BaseModel):
    headline: str
    strengths: list[str]
    weaknesses: list[str]
    data_quality: str


class PulseRead(BaseModel):
    place_id: int
    pulse: float
    dimensions: PulseDimensionsRead
    confidence: PulseConfidenceRead
    trend: PulseTrendRead
    interpretation: PulseInterpretationRead
