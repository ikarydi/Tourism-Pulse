"""Rank a region's official tourism-pressure indicators against Europe.

For each indicator (see ingestion.eurostat_regional) this takes the
region's latest year and places it among every region at the same NUTS
level with a value for that same year. The pressure score is the mean of
those percentiles: a relative, transparent measure ("where does this
destination sit among Europe's regions?") rather than an absolute
carrying-capacity threshold, which no official source defines.

Deterministic, like the Pulse engine (spec section 24): no model, no LLM.
"""

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import NutsRegion, RegionalIndicator

INDICATOR_LABELS: dict[str, str] = {
    "tourism_intensity": "Tourism intensity",
    "tourism_density": "Tourism density",
    "seasonality_peak_share": "Peak-month concentration",
}

INDICATOR_DEFINITIONS: dict[str, str] = {
    "tourism_intensity": "Nights spent per 1,000 residents in a year.",
    "tourism_density": "Nights spent per km² in a year.",
    "seasonality_peak_share": (
        "Share of the year's nights falling in its busiest month "
        "(an even spread would be 8.3%)."
    ),
}

LEVEL_NAMES = {2: "country", 3: "NUTS 1 region", 4: "NUTS 2 region", 5: "NUTS 3 region"}

# Percentile bands: "high" means among the top 30% of comparable regions.
HIGH_FROM = 70.0
MODERATE_FROM = 40.0

METHOD = (
    "Mean of the destination region's percentile ranks on tourism "
    "intensity, tourism density and peak-month concentration, each among "
    "all European regions at the same NUTS level with data for the same "
    "year (Eurostat). 70+ = high, 40-70 = moderate, below 40 = low."
)


@dataclass(frozen=True)
class IndicatorReading:
    indicator: str
    label: str
    definition: str
    value: float
    unit: str
    year: int
    percentile: float  # 0-100, share of peers with a lower value (ties count half)
    rank: int  # 1 = highest pressure among peers
    peers: int
    source: str
    source_observation_id: int | None


@dataclass(frozen=True)
class PressureReading:
    nuts_code: str
    region_name: str | None
    level_name: str
    indicators: list[IndicatorReading]
    score: float | None
    level: str | None
    method: str = METHOD


def pressure_level(score: float) -> str:
    if score >= HIGH_FROM:
        return "high"
    if score >= MODERATE_FROM:
        return "moderate"
    return "low"


def _reading(db: Session, nuts_code: str, indicator: str) -> IndicatorReading | None:
    latest = (
        db.query(RegionalIndicator)
        .filter(RegionalIndicator.nuts_code == nuts_code, RegionalIndicator.indicator == indicator)
        .order_by(RegionalIndicator.year.desc())
        .first()
    )
    if latest is None:
        return None

    peer_values = [
        value
        for (value,) in db.query(RegionalIndicator.value).filter(
            RegionalIndicator.indicator == indicator,
            RegionalIndicator.year == latest.year,
            func.length(RegionalIndicator.nuts_code) == len(nuts_code),
        )
    ]
    lower = sum(value < latest.value for value in peer_values)
    equal = sum(value == latest.value for value in peer_values)
    higher = len(peer_values) - lower - equal

    return IndicatorReading(
        indicator=indicator,
        label=INDICATOR_LABELS[indicator],
        definition=INDICATOR_DEFINITIONS[indicator],
        value=latest.value,
        unit=latest.unit,
        year=latest.year,
        percentile=round(100 * (lower + 0.5 * equal) / len(peer_values), 1),
        rank=higher + 1,
        peers=len(peer_values),
        source=latest.source,
        source_observation_id=latest.source_observation_id,
    )


def pressure_for_region(db: Session, nuts_code: str) -> PressureReading:
    readings = [
        reading
        for indicator in INDICATOR_LABELS
        if (reading := _reading(db, nuts_code, indicator)) is not None
    ]
    score = (
        round(sum(reading.percentile for reading in readings) / len(readings), 1)
        if readings
        else None
    )
    region = db.get(NutsRegion, nuts_code)
    return PressureReading(
        nuts_code=nuts_code,
        region_name=region.name if region is not None else None,
        level_name=LEVEL_NAMES.get(len(nuts_code), "region"),
        indicators=readings,
        score=score,
        level=pressure_level(score) if score is not None else None,
    )
