"""Map airports to places and upsert monthly flight signals."""

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, Signal, SignalBreakdown
from tourism_pulse_api.ingestion.eurocontrol.parser import (
    STATE_CODES,
    Airport,
    matched_growth,
    nearby,
)

SOURCE_NAME = "eurocontrol"
SOURCE_URL = "https://ansperformance.eu/reference/dataset/airport-traffic/"
ARRIVALS = "flight_arrivals"
GROWTH = "flight_arrivals_growth"
# Airports within this distance of a curated destination serve it (Venice:
# VCE and Treviso; Brussels: BRU and Charleroi; Paris: CDG and Orly).
DESTINATION_RADIUS_KM = 50.0
_BATCH_ROWS = 1000


@dataclass
class PlaceAirports:
    """place id -> ICAO codes, and the places that also get an airport
    breakdown (countries and destinations: regions have one or two)."""

    airports: dict[int, set[str]] = field(default_factory=lambda: defaultdict(set))
    with_breakdown: set[int] = field(default_factory=set)


def _regions_containing(db: Session, airports: dict[str, Airport]) -> dict[str, list[str]]:
    """ICAO -> NUTS codes (levels 2 and 3) whose shape contains the airport."""
    if not airports:
        return {}
    values = ", ".join(f"(:icao{i}, :lon{i}, :lat{i})" for i in range(len(airports)))
    params: dict[str, object] = {}
    for i, airport in enumerate(airports.values()):
        params[f"icao{i}"] = airport.icao
        params[f"lon{i}"] = airport.longitude
        params[f"lat{i}"] = airport.latitude
    rows = db.execute(
        text(
            f"""
            select a.icao, r.code
            from (values {values}) as a(icao, lon, lat)
            join nuts_regions r
              on r.level in (2, 3)
             and ST_Contains(r.geom, ST_SetSRID(ST_MakePoint(a.lon, a.lat), 4326))
            """  # noqa: S608 - only bind-parameter placeholders are interpolated
        ),
        params,
    )
    out: dict[str, list[str]] = defaultdict(list)
    for icao, code in rows:
        out[icao].append(code)
    return out


def map_airports(
    db: Session, monthly: pd.DataFrame, coordinates: dict[str, Airport]
) -> PlaceAirports:
    mapping = PlaceAirports()
    by_country: dict[str, set[str]] = defaultdict(set)
    for icao, country in zip(monthly["icao"], monthly["country"], strict=True):
        by_country[country].add(icao)
    # Destinations and regions count visitor gateways only; national totals
    # keep every airport, as research/gate3 does.
    gateways = {icao: airport for icao, airport in coordinates.items() if airport.scheduled}
    regions = _regions_containing(db, gateways)
    by_region: dict[str, set[str]] = defaultdict(set)
    for icao, codes in regions.items():
        for code in codes:
            by_region[code].add(icao)

    for place in db.query(Place).filter(
        Place.place_type.in_(["country", "destination", "region", "area"])
    ):
        if place.place_type == "country" and place.nuts_code in STATE_CODES.values():
            found = by_country.get(place.nuts_code, set())
            breakdown = True
        elif place.place_type == "destination":
            if place.latitude is None or place.longitude is None:
                continue
            found = set(nearby(place.latitude, place.longitude, gateways, DESTINATION_RADIUS_KM))
            breakdown = True
        elif place.place_type == "region" and place.nuts_code:
            found, breakdown = by_region.get(place.nuts_code, set()), False
        elif place.place_type == "area" and place.nuts3_code:
            found, breakdown = by_region.get(place.nuts3_code, set()), False
        else:
            continue
        if found:
            mapping.airports[place.id] = set(found)
            if breakdown:
                mapping.with_breakdown.add(place.id)
    return mapping


def _month_end(month: pd.Period) -> datetime:
    last = calendar.monthrange(month.year, month.month)[1]
    return datetime(month.year, month.month, last, tzinfo=UTC)


@dataclass
class Written:
    signals: int = 0
    breakdowns: int = 0
    places: int = 0


def upsert_flights(
    db: Session,
    monthly: pd.DataFrame,
    mapping: PlaceAirports,
    *,
    since: pd.Period,
    source_observation_id: int | None,
) -> Written:
    """Signals for months from `since` (growth needs the full history, so
    `monthly` should reach back a year before it)."""
    signals: list[dict] = []
    breakdowns: list[dict] = []
    arrivals: dict[tuple[str, pd.Period], float] = {
        (icao, month): float(value)
        for icao, month, value in zip(
            monthly["icao"], monthly["month"], monthly["arrivals"], strict=True
        )
    }
    months_by_airport: dict[str, list[pd.Period]] = defaultdict(list)
    for icao, month in arrivals:
        months_by_airport[icao].append(month)

    for place_id, icaos in mapping.airports.items():
        totals: dict[pd.Period, float] = defaultdict(float)
        for icao in icaos:
            for month in months_by_airport.get(icao, []):
                if month < since:
                    continue
                value = arrivals[(icao, month)]
                totals[month] += value
                if place_id in mapping.with_breakdown:
                    breakdowns.append(
                        {
                            "place_id": place_id,
                            "signal_type": ARRIVALS,
                            "observed_at": _month_end(month),
                            "dimension": "airport",
                            "key": icao,
                            "value": value,
                            "source": SOURCE_NAME,
                        }
                    )
        for month, total in totals.items():
            signals.append(
                _signal(place_id, ARRIVALS, total, "flights", month, source_observation_id)
            )
        for month, change in matched_growth(monthly, icaos).items():
            if month >= since:
                signals.append(
                    _signal(place_id, GROWTH, 100 * change, "percent", month, source_observation_id)
                )

    for start in range(0, len(signals), _BATCH_ROWS):
        statement = insert(Signal).values(signals[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            constraint="uq_signals_place_type_observed_source",
            set_={
                "value": statement.excluded.value,
                "unit": statement.excluded.unit,
                "source_observation_id": statement.excluded.source_observation_id,
            },
        )
        db.execute(statement)
    for start in range(0, len(breakdowns), _BATCH_ROWS):
        statement = insert(SignalBreakdown).values(breakdowns[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            constraint="uq_signal_breakdowns_place_type_observed_dimension_key",
            set_={"value": statement.excluded.value},
        )
        db.execute(statement)
    db.commit()
    return Written(len(signals), len(breakdowns), len(mapping.airports))


def _signal(
    place_id: int,
    signal_type: str,
    value: float,
    unit: str,
    month: pd.Period,
    source_observation_id: int | None,
) -> dict:
    return {
        "place_id": place_id,
        "signal_type": signal_type,
        "value": value,
        "unit": unit,
        "observed_at": _month_end(month),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "source_observation_id": source_observation_id,
    }
