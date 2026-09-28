"""Mirrors insights.economy (see its module docstring)."""

from pydantic import BaseModel


class AirportArrivalsRead(BaseModel):
    icao: str
    arrivals: float


class FlightPointRead(BaseModel):
    period: str
    arrivals: float | None
    growth: float | None


class FlightsRead(BaseModel):
    latest_period: str
    arrivals: float
    growth: float | None
    growth_3m: float | None
    airports: list[AirportArrivalsRead]
    series: list[FlightPointRead]


class SurveyPointRead(BaseModel):
    period: str
    demand_expected: float | None
    demand_past: float | None


class SurveyRead(BaseModel):
    latest_period: str
    confidence: float | None
    demand_past: float | None
    demand_expected: float | None
    demand_expected_year_ago: float | None
    employment_expected: float | None
    prices_expected: float | None
    travel_trade_demand_expected: float | None
    series: list[SurveyPointRead]
    # The latest month is over four months old (Spain stopped in 2024-09).
    stale: bool = False


class PricePointRead(BaseModel):
    period: str
    accommodation: float | None
    all_items: float | None


class PricesRead(BaseModel):
    latest_period: str
    accommodation: float | None
    restaurants: float | None
    air_fares: float | None
    all_items: float | None
    series: list[PricePointRead]


class TurnoverRead(BaseModel):
    latest_period: str
    accommodation: float | None
    food_service: float | None


class OriginShareRead(BaseModel):
    key: str
    name: str
    nights: float
    share: float
    previous_share: float | None


class OriginsRead(BaseModel):
    year: int
    total_nights: float
    domestic_share: float | None
    foreign_nights: float
    top: list[OriginShareRead]


class EconomyRead(BaseModel):
    place_id: int
    place_name: str
    national_place_id: int | None
    national_place_name: str | None
    flights: FlightsRead | None
    survey: SurveyRead | None
    prices: PricesRead | None
    turnover: TurnoverRead | None
    origins: OriginsRead | None
    highlights: list[str]
