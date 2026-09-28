from datetime import datetime

from pydantic import BaseModel


class ForecastPointRead(BaseModel):
    period: str
    horizon: int
    point: float
    low_80: float
    high_80: float
    low_95: float
    high_95: float
    last_year: float | None


class HistoryPointRead(BaseModel):
    period: str
    value: float


class OutlookRead(BaseModel):
    months: int
    forecast: float
    last_year: float
    change: float
    low_80: float
    high_80: float


class HorizonAccuracyRead(BaseModel):
    horizon: int
    mape: float
    scored: int


class AccuracyRead(BaseModel):
    scored: int
    mape: float | None
    coverage_80: float | None
    by_horizon: list[HorizonAccuracyRead]


class ValidationRead(BaseModel):
    study: str
    mape: float
    seasonal_naive_mape: float
    countries_better_than_last_year: int
    countries_attention_helps: int
    countries: int
    coverage_80: float


class PlaceForecastRead(BaseModel):
    place_id: int
    signal_type: str
    unit: str
    model: str
    validated: bool
    method: str
    validation: ValidationRead | None
    issued_at: datetime
    origin: str
    history: list[HistoryPointRead]
    points: list[ForecastPointRead]
    outlook: list[OutlookRead]
    backtest: AccuracyRead | None
    track_record: AccuracyRead | None


class ForecastSummaryRead(BaseModel):
    place_id: int
    name: str
    place_type: str
    country_code: str | None
    origin: str
    model: str
    validated: bool
    next_3_change: float | None
    next_12_change: float | None
    next_12_nights: float | None
    backtest_mape: float | None
    live_scored: int
    live_mape: float | None
