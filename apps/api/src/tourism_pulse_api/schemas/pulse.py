from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class EvidenceSignalRead(BaseModel):
    id: int
    signal_type: str
    source: str
    value: float
    unit: str | None = None
    observed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceArticleRead(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceVideoRead(BaseModel):
    title: str
    video_id: str
    channel: str | None = None
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceEventRead(BaseModel):
    id: int
    name: str
    event_type: str
    start_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DimensionEvidenceRead(BaseModel):
    dimension: str
    value: float
    contributing_signals: list[EvidenceSignalRead]
    related_articles: list[EvidenceArticleRead]
    related_videos: list[EvidenceVideoRead]
    related_events: list[EvidenceEventRead]

    model_config = ConfigDict(from_attributes=True)


class PulseRead(BaseModel):
    place_id: int
    pulse: float
    dimensions: PulseDimensionsRead
    confidence: PulseConfidenceRead
    # Tourism-pressure score (0-100, higher = more strain): the mean
    # European percentile of the place's official regional indicators
    # (see /places/{id}/observatory). Reported beside the Pulse, never
    # blended into it. None when the place has no regional data.
    pressure: float | None = None
    trend: PulseTrendRead
    interpretation: PulseInterpretationRead
    # Both optional: only computed on the persist=true path (the "real"
    # calculation, not bulk/overview browsing - see routers/pulse.py), and
    # narrative is additionally None whenever no LLM provider is configured
    # (pulse.narrative degrades gracefully, same pattern as e.g. OpenAQ's
    # optional API key).
    evidence: dict[str, DimensionEvidenceRead] | None = None
    narrative: str | None = None
