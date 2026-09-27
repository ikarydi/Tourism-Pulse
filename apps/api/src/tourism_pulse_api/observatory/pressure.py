"""Rank a destination's official tourism-pressure indicators against Europe.

For each indicator (see ingestion.eurostat_regional) this uses the finest
region with data - the destination's NUTS 3 region, else its NUTS 2
region (or, for a country, its national code) - takes that region's
latest year, and places it among every region at the same NUTS level
with a value for that same year. The pressure score is the mean of those
percentiles: a relative, transparent measure ("where does this
destination sit among Europe's regions?") rather than an absolute
carrying-capacity threshold, which no official source defines.

Deterministic, like the Pulse engine (spec section 24): no model, no LLM.
"""

from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import NutsRegion, Place, RegionalIndicator

INDICATOR_LABELS: dict[str, str] = {
    "tourism_intensity": "Tourism intensity",
    "tourism_density": "Tourism density",
    "seasonality_peak_share": "Peak-month concentration",
    "str_share": "Short-term rental share",
}

INDICATOR_DEFINITIONS: dict[str, str] = {
    "tourism_intensity": "Nights spent per 1,000 residents in a year.",
    "tourism_density": "Nights spent per km² in a year.",
    "seasonality_peak_share": (
        "Share of the year's nights falling in its busiest month (an even spread would be 8.3%)."
    ),
    "str_share": (
        "Nights booked through online platforms (Airbnb, Booking.com, Expedia, "
        "Tripadvisor) as a share of platform plus official accommodation nights. "
        "Approximate: some platform-listed properties are also counted in "
        "official statistics."
    ),
}

LEVEL_NAMES = {2: "country", 3: "NUTS 1 region", 4: "NUTS 2 region", 5: "NUTS 3 region"}

# Percentile bands: "high" means among the top 30% of comparable regions.
HIGH_FROM = 70.0
MODERATE_FROM = 40.0

METHOD = (
    "Mean of the destination's percentile ranks on tourism intensity, "
    "tourism density, peak-month concentration and short-term rental "
    "share. Each indicator uses the finest region with data (NUTS 3, else "
    "NUTS 2) and is ranked among all European regions at that level with "
    "data for the same year (Eurostat). 70+ = high, 40-70 = moderate, "
    "below 40 = low."
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
    region_code: str
    region_name: str | None
    level_name: str


@dataclass(frozen=True)
class PressureReading:
    nuts_code: str
    region_name: str | None
    level_name: str
    indicators: list[IndicatorReading]
    score: float | None
    level: str | None
    method: str = METHOD


@dataclass
class PeerCache:
    """Peer values per (indicator, year, code length), shared across the
    places ranked in one request - the overview ranks every place."""

    values: dict[tuple[str, int, int], list[float]] = field(default_factory=dict)

    def peers(self, db: Session, indicator: str, year: int, code_length: int) -> list[float]:
        key = (indicator, year, code_length)
        if key not in self.values:
            self.values[key] = [
                value
                for (value,) in db.query(RegionalIndicator.value).filter(
                    RegionalIndicator.indicator == indicator,
                    RegionalIndicator.year == year,
                    func.length(RegionalIndicator.nuts_code) == code_length,
                )
            ]
        return self.values[key]


def pressure_level(score: float) -> str:
    if score >= HIGH_FROM:
        return "high"
    if score >= MODERATE_FROM:
        return "moderate"
    return "low"


def _region_name(db: Session, code: str) -> str | None:
    region = db.get(NutsRegion, code)
    return region.name if region is not None else None


def _reading(
    db: Session, codes: list[str], indicator: str, cache: PeerCache
) -> IndicatorReading | None:
    """The indicator at the first (finest) code that has data."""
    for code in codes:
        latest = (
            db.query(RegionalIndicator)
            .filter(RegionalIndicator.nuts_code == code, RegionalIndicator.indicator == indicator)
            .order_by(RegionalIndicator.year.desc())
            .first()
        )
        if latest is None:
            continue

        peer_values = cache.peers(db, indicator, latest.year, len(code))
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
            region_code=code,
            region_name=_region_name(db, code),
            level_name=LEVEL_NAMES.get(len(code), "region"),
        )
    return None


def pressure_for_codes(
    db: Session, codes: list[str], cache: PeerCache | None = None
) -> PressureReading:
    """`codes` from finest to coarsest, e.g. [NUTS 3, NUTS 2]."""
    cache = cache or PeerCache()
    readings = [
        reading
        for indicator in INDICATOR_LABELS
        if (reading := _reading(db, codes, indicator, cache)) is not None
    ]
    score = (
        round(sum(reading.percentile for reading in readings) / len(readings), 1)
        if readings
        else None
    )
    # Headline region: the finest one any indicator actually used.
    used = [code for code in codes if any(r.region_code == code for r in readings)]
    headline = used[0] if used else codes[0]
    return PressureReading(
        nuts_code=headline,
        region_name=_region_name(db, headline),
        level_name=LEVEL_NAMES.get(len(headline), "region"),
        indicators=readings,
        score=score,
        level=pressure_level(score) if score is not None else None,
    )


def pressure_for_region(db: Session, nuts_code: str) -> PressureReading:
    return pressure_for_codes(db, [nuts_code])


def place_codes(place: Place) -> list[str]:
    return [code for code in (place.nuts3_code, place.nuts_code) if code]


def pressure_for_place(
    db: Session, place: Place, cache: PeerCache | None = None
) -> PressureReading | None:
    codes = place_codes(place)
    return pressure_for_codes(db, codes, cache) if codes else None
