"""Inbound travel and economic context for one place.

Deterministic, like the attention insights: no model, no LLM. Flights are
the place's own (its airports). The survey, prices, turnover and origin
markets are national figures, taken from the country the place is in, and
labelled as such.

None of this feeds the Pulse or the pressure score. Whether flights and the
survey improve the outlook is Gate 3's question (research/gate3/).
"""

import calendar
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, Signal, SignalBreakdown
from tourism_pulse_api.ingestion.eurostat.parser import eurostat_geo_code

SERIES_MONTHS = 36
TOP_ORIGINS = 8
# The survey is stale once its latest month is this far behind (Spain's
# accommodation series stopped in September 2024).
STALE_AFTER_MONTHS = 4
# Year-on-year shifts in the survey balance smaller than this read as "about
# the same".
SURVEY_SHIFT_POINTS = 3.0

ORIGIN_NAMES: dict[str, str] = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus", "CZ": "Czechia",
    "DE": "Germany", "DK": "Denmark", "EE": "Estonia", "EL": "Greece", "ES": "Spain",
    "FI": "Finland", "FR": "France", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland",
    "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SE": "Sweden",
    "SI": "Slovenia", "SK": "Slovakia", "IS": "Iceland", "NO": "Norway",
    "CH": "Switzerland and Liechtenstein", "UK": "United Kingdom", "TR": "Türkiye",
    "UA": "Ukraine", "RU": "Russia", "ZA": "South Africa", "CA": "Canada",
    "US": "United States", "BR": "Brazil", "CN": "China", "JP": "Japan",
    "KR": "South Korea", "AU": "Australia",
}  # fmt: skip

FLIGHT_TYPES = ("flight_arrivals", "flight_arrivals_growth")
NATIONAL_TYPES = (
    "hotel_confidence",
    "hotel_demand_past",
    "hotel_demand_expected",
    "hotel_employment_expected",
    "hotel_prices_expected",
    "travel_trade_demand_expected",
    "price_change_all",
    "price_change_accommodation",
    "price_change_restaurants",
    "price_change_air_fares",
    "accommodation_turnover_index",
    "food_service_turnover_index",
)


@dataclass(frozen=True)
class AirportArrivals:
    icao: str
    arrivals: float


@dataclass(frozen=True)
class FlightPoint:
    period: str
    arrivals: float | None
    growth: float | None


@dataclass
class FlightsInsight:
    latest_period: str
    arrivals: float
    # Percent against the same month a year earlier, same airports.
    growth: float | None
    growth_3m: float | None
    airports: list[AirportArrivals]
    series: list[FlightPoint]


@dataclass(frozen=True)
class SurveyPoint:
    period: str
    demand_expected: float | None
    demand_past: float | None


@dataclass
class SurveyInsight:
    latest_period: str
    confidence: float | None
    demand_past: float | None
    demand_expected: float | None
    demand_expected_year_ago: float | None
    employment_expected: float | None
    prices_expected: float | None
    travel_trade_demand_expected: float | None
    series: list[SurveyPoint]
    stale: bool = False


@dataclass(frozen=True)
class PricePoint:
    period: str
    accommodation: float | None
    all_items: float | None


@dataclass
class PricesInsight:
    latest_period: str
    # Percent against the same month a year earlier.
    accommodation: float | None
    restaurants: float | None
    air_fares: float | None
    all_items: float | None
    series: list[PricePoint]


@dataclass
class TurnoverInsight:
    latest_period: str
    # Percent against the same month a year earlier, from the index.
    accommodation: float | None
    food_service: float | None


@dataclass(frozen=True)
class OriginShare:
    key: str
    name: str
    nights: float
    # Share of foreign nights, and the same share a year earlier.
    share: float
    previous_share: float | None


@dataclass
class OriginsInsight:
    year: int
    total_nights: float
    domestic_share: float | None
    foreign_nights: float
    top: list[OriginShare]


@dataclass
class EconomyInsight:
    place_id: int
    place_name: str
    # The country whose national figures are shown (the place itself for a
    # country).
    national_place_id: int | None
    national_place_name: str | None
    flights: FlightsInsight | None
    survey: SurveyInsight | None
    prices: PricesInsight | None
    turnover: TurnoverInsight | None
    origins: OriginsInsight | None
    highlights: list[str] = field(default_factory=list)


def _period(moment: datetime) -> str:
    return f"{moment:%Y-%m}"


def _month_label(period: str) -> str:
    return datetime.strptime(period, "%Y-%m").strftime("%B %Y")


def _month_end(period: str) -> datetime:
    """Monthly signals are stored at the last day of their month (UTC)."""
    year, month = int(period[:4]), int(period[5:7])
    return datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=UTC)


def _shift(period: str, months: int) -> str:
    year, month = int(period[:4]), int(period[5:7])
    index = year * 12 + (month - 1) + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def country_place(db: Session, place: Place) -> Place | None:
    """The EU27 country place a place belongs to."""
    if place.place_type == "country":
        return place
    code: str | None = None
    if place.destination is not None and place.destination.country_code:
        code = eurostat_geo_code(place.destination.country_code)
    elif place.nuts_code:
        code = place.nuts_code[:2]
    elif place.nuts3_code:
        code = place.nuts3_code[:2]
    elif place.urau_code:
        code = place.urau_code[:2]
    if not code:
        return None
    return (
        db.query(Place)
        .filter(Place.place_type == "country", Place.nuts_code == code)
        .order_by(Place.id)
        .first()
    )


def _series(db: Session, place_id: int, types: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """signal_type -> period -> value."""
    out: dict[str, dict[str, float]] = {signal_type: {} for signal_type in types}
    for signal_type, observed_at, value in (
        db.query(Signal.signal_type, Signal.observed_at, Signal.value)
        .filter(Signal.place_id == place_id, Signal.signal_type.in_(types))
        .order_by(Signal.observed_at)
    ):
        out[signal_type][_period(observed_at)] = float(value)
    return out


def _flights(db: Session, place: Place) -> FlightsInsight | None:
    series = _series(db, place.id, FLIGHT_TYPES)
    arrivals, growth = series["flight_arrivals"], series["flight_arrivals_growth"]
    if not arrivals:
        return None
    latest = max(arrivals)
    recent = [growth[p] for p in (_shift(latest, -k) for k in range(3)) if p in growth]
    airports = [
        AirportArrivals(key, float(value))
        for key, value in db.query(SignalBreakdown.key, SignalBreakdown.value)
        .filter(
            SignalBreakdown.place_id == place.id,
            SignalBreakdown.signal_type == "flight_arrivals",
            SignalBreakdown.dimension == "airport",
            SignalBreakdown.observed_at == _month_end(latest),
        )
        .order_by(SignalBreakdown.value.desc())
    ]
    periods = sorted(arrivals)[-SERIES_MONTHS:]
    return FlightsInsight(
        latest_period=latest,
        arrivals=arrivals[latest],
        growth=growth.get(latest),
        growth_3m=sum(recent) / len(recent) if len(recent) == 3 else None,
        airports=airports,
        series=[FlightPoint(p, arrivals.get(p), growth.get(p)) for p in periods],
    )


def _latest(values: dict[str, float]) -> str | None:
    return max(values) if values else None


def _survey(national: dict[str, dict[str, float]], today: date) -> SurveyInsight | None:
    expected = national["hotel_demand_expected"]
    latest = _latest(expected)
    if latest is None:
        return None
    stale = latest < _shift(f"{today:%Y-%m}", -STALE_AFTER_MONTHS)
    periods = sorted(expected)[-SERIES_MONTHS:]
    return SurveyInsight(
        latest_period=latest,
        confidence=national["hotel_confidence"].get(latest),
        demand_past=national["hotel_demand_past"].get(latest),
        demand_expected=expected[latest],
        demand_expected_year_ago=expected.get(_shift(latest, -12)),
        employment_expected=national["hotel_employment_expected"].get(latest),
        prices_expected=national["hotel_prices_expected"].get(latest),
        travel_trade_demand_expected=national["travel_trade_demand_expected"].get(latest),
        series=[
            SurveyPoint(p, expected.get(p), national["hotel_demand_past"].get(p)) for p in periods
        ],
        stale=stale,
    )


def _prices(national: dict[str, dict[str, float]]) -> PricesInsight | None:
    accommodation = national["price_change_accommodation"]
    latest = _latest(accommodation)
    if latest is None:
        return None
    periods = sorted(accommodation)[-SERIES_MONTHS:]
    return PricesInsight(
        latest_period=latest,
        accommodation=accommodation[latest],
        restaurants=national["price_change_restaurants"].get(latest),
        air_fares=national["price_change_air_fares"].get(latest),
        all_items=national["price_change_all"].get(latest),
        series=[
            PricePoint(p, accommodation.get(p), national["price_change_all"].get(p))
            for p in periods
        ],
    )


def _change(index: dict[str, float], period: str) -> float | None:
    now, before = index.get(period), index.get(_shift(period, -12))
    if now is None or before is None or before <= 0:
        return None
    return 100 * (now / before - 1)


def _turnover(national: dict[str, dict[str, float]]) -> TurnoverInsight | None:
    accommodation = national["accommodation_turnover_index"]
    latest = _latest(accommodation)
    if latest is None:
        return None
    return TurnoverInsight(
        latest_period=latest,
        accommodation=_change(accommodation, latest),
        food_service=_change(national["food_service_turnover_index"], latest),
    )


def _origins(db: Session, country: Place) -> OriginsInsight | None:
    by_year: dict[int, dict[str, float]] = {}
    for observed_at, key, value in db.query(
        SignalBreakdown.observed_at, SignalBreakdown.key, SignalBreakdown.value
    ).filter(
        SignalBreakdown.place_id == country.id,
        SignalBreakdown.signal_type == "tourism_nights_annual",
        SignalBreakdown.dimension == "origin",
    ):
        by_year.setdefault(observed_at.year, {})[key] = float(value)
    if not by_year:
        return None
    year = max(by_year)
    parts = by_year[year]
    # The country's own code repeats "domestic" in older loads.
    own = {"domestic", country.nuts_code}
    foreign = {key: value for key, value in parts.items() if key not in own}
    foreign_total = sum(foreign.values())
    if foreign_total <= 0:
        return None
    before = {k: v for k, v in by_year.get(year - 1, {}).items() if k not in own}
    before_total = sum(before.values())
    domestic = parts.get("domestic")
    total = foreign_total + (domestic or 0.0)
    top = sorted(foreign.items(), key=lambda item: -item[1])[:TOP_ORIGINS]
    return OriginsInsight(
        year=year,
        total_nights=total,
        domestic_share=domestic / total if domestic is not None and total > 0 else None,
        foreign_nights=foreign_total,
        top=[
            OriginShare(
                key=key,
                name=ORIGIN_NAMES.get(key, key),
                nights=value,
                share=value / foreign_total,
                previous_share=(
                    before[key] / before_total if before_total > 0 and key in before else None
                ),
            )
            for key, value in top
        ],
    )


def _signed(value: float, digits: int = 1) -> str:
    return f"{'+' if value >= 0 else '−'}{abs(value):.{digits}f}"


def _highlights(insight: EconomyInsight) -> list[str]:
    out: list[str] = []
    flights = insight.flights
    if flights and flights.growth is not None:
        out.append(
            f"Flight arrivals in {_month_label(flights.latest_period)}: "
            f"{_signed(flights.growth)}% on a year earlier at the same airports."
        )
    country = insight.national_place_name or "the country"
    survey = insight.survey
    if (
        survey
        and not survey.stale
        and survey.demand_expected is not None
        and survey.demand_expected_year_ago is not None
    ):
        # The balance is seasonal, so only the same month a year earlier is
        # a fair comparison.
        shift = survey.demand_expected - survey.demand_expected_year_ago
        if abs(shift) < SURVEY_SHIFT_POINTS:
            mood = "about as optimistic about the next three months as a year earlier"
        elif shift > 0:
            mood = "more optimistic about the next three months than a year earlier"
        else:
            mood = "less optimistic about the next three months than a year earlier"
        out.append(
            f"Hotels in {country} are {mood}: an expected-demand balance of "
            f"{_signed(survey.demand_expected, 0)} in {_month_label(survey.latest_period)}, "
            f"against {_signed(survey.demand_expected_year_ago, 0)} a year before."
        )
    prices = insight.prices
    if prices and prices.accommodation is not None:
        text = (
            f"Accommodation prices in {country}: {_signed(prices.accommodation)}% on a year "
            f"earlier in {_month_label(prices.latest_period)}"
        )
        if prices.all_items is not None:
            text += f", against {_signed(prices.all_items)}% for all consumer prices"
        out.append(text + ".")
    turnover = insight.turnover
    if turnover and turnover.accommodation is not None:
        out.append(
            f"Accommodation turnover in {country}: {_signed(turnover.accommodation)}% on a "
            f"year earlier in {_month_label(turnover.latest_period)}."
        )
    origins = insight.origins
    if origins and origins.top:
        leaders = ", ".join(f"{o.name} {o.share:.0%}" for o in origins.top[:3])
        out.append(f"Largest foreign markets in {origins.year}: {leaders} of foreign nights.")
    return out


def economy_for_place(db: Session, place: Place, today: date | None = None) -> EconomyInsight:
    today = today or date.today()
    country = country_place(db, place)
    national = _series(db, country.id, NATIONAL_TYPES) if country else None
    insight = EconomyInsight(
        place_id=place.id,
        place_name=place.name,
        national_place_id=country.id if country else None,
        national_place_name=country.name if country else None,
        flights=_flights(db, place),
        survey=_survey(national, today) if national else None,
        prices=_prices(national) if national else None,
        turnover=_turnover(national) if national else None,
        origins=_origins(db, country) if country else None,
    )
    insight.highlights = _highlights(insight)
    return insight
