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

from bisect import bisect_left, bisect_right
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

# Economic dependence, reported beside the pressure score and never part of
# it: how much of the region's economy sits in the sectors visitors use.
DEPENDENCE_LABELS: dict[str, str] = {
    "gva_share_g_i": "Output in trade, transport and hospitality",
    "employment_share_g_i": "Jobs in trade, transport and hospitality",
}

DEPENDENCE_DEFINITIONS: dict[str, str] = {
    "gva_share_g_i": (
        "Gross value added in wholesale and retail trade, transport, accommodation and "
        "food service (NACE G-I) as a share of the region's total. Broader than tourism: "
        "Eurostat's regional accounts have no finer split."
    ),
    "employment_share_g_i": (
        "People employed in the same sectors as a share of all employed residents "
        "(labour force survey, NUTS 2 at the finest)."
    ),
}

_LABELS = {**INDICATOR_LABELS, **DEPENDENCE_LABELS}
_DEFINITIONS = {**INDICATOR_DEFINITIONS, **DEPENDENCE_DEFINITIONS}

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
    dependence: list[IndicatorReading] = field(default_factory=list)


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


def _make_reading(
    *,
    indicator: str,
    row: RegionalIndicator | tuple,
    code: str,
    lower: int,
    equal: int,
    peers: int,
    region_name: str | None,
) -> IndicatorReading:
    value, unit, year, source, observation_id = (
        (row.value, row.unit, row.year, row.source, row.source_observation_id)
        if isinstance(row, RegionalIndicator)
        else row
    )
    return IndicatorReading(
        indicator=indicator,
        label=_LABELS[indicator],
        definition=_DEFINITIONS[indicator],
        value=value,
        unit=unit,
        year=year,
        percentile=round(100 * (lower + 0.5 * equal) / peers, 1),
        rank=peers - lower - equal + 1,
        peers=peers,
        source=source,
        source_observation_id=observation_id,
        region_code=code,
        region_name=region_name,
        level_name=LEVEL_NAMES.get(len(code), "region"),
    )


def _assemble(
    codes: list[str],
    readings: list[IndicatorReading],
    region_name,
    dependence: list[IndicatorReading] | None = None,
) -> PressureReading:
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
        region_name=region_name(headline),
        level_name=LEVEL_NAMES.get(len(headline), "region"),
        indicators=readings,
        score=score,
        level=pressure_level(score) if score is not None else None,
        dependence=dependence or [],
    )


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
        return _make_reading(
            indicator=indicator,
            row=latest,
            code=code,
            lower=sum(value < latest.value for value in peer_values),
            equal=sum(value == latest.value for value in peer_values),
            peers=len(peer_values),
            region_name=_region_name(db, code),
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
    dependence = [
        reading
        for indicator in DEPENDENCE_LABELS
        if (reading := _reading(db, codes, indicator, cache)) is not None
    ]
    return _assemble(codes, readings, lambda code: _region_name(db, code), dependence)


def pressure_for_region(db: Session, nuts_code: str) -> PressureReading:
    return pressure_for_codes(db, [nuts_code])


def place_codes(place: Place) -> list[str]:
    return [code for code in (place.nuts3_code, place.nuts_code) if code]


def pressure_for_place(
    db: Session, place: Place, cache: PeerCache | None = None
) -> PressureReading | None:
    codes = place_codes(place)
    return pressure_for_codes(db, codes, cache) if codes else None


class Ranker:
    """Every region's readings from one pass over regional_indicators.

    Same results as pressure_for_codes (shared _make_reading/_assemble),
    for ranking thousands of places at once: the per-place path issues
    several queries per indicator, which is fine for one destination page
    and far too slow for an overview of every EU region.
    """

    def __init__(self, db: Session) -> None:
        latest: dict[tuple[str, str], tuple] = {}
        peers: dict[tuple[str, int, int], list[float]] = {}
        for code, indicator, year, value, unit, source, observation_id in db.query(
            RegionalIndicator.nuts_code,
            RegionalIndicator.indicator,
            RegionalIndicator.year,
            RegionalIndicator.value,
            RegionalIndicator.unit,
            RegionalIndicator.source,
            RegionalIndicator.source_observation_id,
        ):
            peers.setdefault((indicator, year, len(code)), []).append(value)
            current = latest.get((code, indicator))
            if current is None or year > current[2]:
                latest[(code, indicator)] = (value, unit, year, source, observation_id)
        self._latest = latest
        self._peers = {key: sorted(values) for key, values in peers.items()}
        self._names = dict(db.query(NutsRegion.code, NutsRegion.name))

    def _reading(self, codes: list[str], indicator: str) -> IndicatorReading | None:
        for code in codes:
            row = self._latest.get((code, indicator))
            if row is None:
                continue
            values = self._peers[(indicator, row[2], len(code))]
            lower = bisect_left(values, row[0])
            return _make_reading(
                indicator=indicator,
                row=row,
                code=code,
                lower=lower,
                equal=bisect_right(values, row[0]) - lower,
                peers=len(values),
                region_name=self._names.get(code),
            )
        return None

    def pressure_for_codes(self, codes: list[str]) -> PressureReading:
        readings = [
            reading
            for indicator in INDICATOR_LABELS
            if (reading := self._reading(codes, indicator)) is not None
        ]
        dependence = [
            reading
            for indicator in DEPENDENCE_LABELS
            if (reading := self._reading(codes, indicator)) is not None
        ]
        return _assemble(codes, readings, self._names.get, dependence)

    def pressure_for_place(self, place: Place) -> PressureReading | None:
        codes = place_codes(place)
        return self.pressure_for_codes(codes) if codes else None
