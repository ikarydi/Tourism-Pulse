from pydantic import BaseModel, ConfigDict


class IndicatorReadingRead(BaseModel):
    indicator: str
    label: str
    definition: str
    value: float
    unit: str
    year: int
    percentile: float
    rank: int
    peers: int
    source: str
    source_observation_id: int | None = None
    # The region this indicator comes from: the finest level with data.
    region_code: str
    region_name: str | None = None
    level_name: str

    model_config = ConfigDict(from_attributes=True)


class ObservatoryRead(BaseModel):
    place_id: int
    # None when the place has no NUTS code yet (see ingestion.nuts).
    nuts_code: str | None = None
    region_name: str | None = None
    level_name: str | None = None
    indicators: list[IndicatorReadingRead] = []
    # Tourism-pressure score, 0-100: mean European percentile of the
    # indicators above. None when no indicator is available.
    score: float | None = None
    level: str | None = None
    method: str | None = None
    # Economic dependence (share of output and jobs in trade, transport and
    # hospitality), ranked the same way but never part of the score.
    dependence: list[IndicatorReadingRead] = []

    model_config = ConfigDict(from_attributes=True)


class ObservatoryRankingRead(ObservatoryRead):
    """One row of the observatory overview (GET /observatory)."""

    place_name: str
    place_type: str
    country_code: str | None = None
