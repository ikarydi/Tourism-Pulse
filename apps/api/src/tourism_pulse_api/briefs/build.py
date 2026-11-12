"""Assemble one destination's Pressure Brief from what the platform
already computes: the pressure observatory, the regional indicator
history, monthly official nights and the 12-month outlook.

Deterministic, like the Pulse engine and the observatory: no model and
no LLM writes any sentence here. Every finding is a rule applied to a
published figure, and every figure names its source and year.

Only sources cleared for commercial reuse (tourism_pulse_api.licensing)
reach a brief. A section that would need any other source is left out
and listed under `withheld`, so a paid document never carries data the
publisher has not licensed for sale.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, Signal
from tourism_pulse_api.forecasting.read import nights_by_place, place_forecast
from tourism_pulse_api.forecasting.service import SIGNAL_TYPE
from tourism_pulse_api.licensing import SourceLicence, licence_for, not_cleared
from tourism_pulse_api.observatory.pressure import (
    DEPENDENCE_LABELS,
    HIGH_FROM,
    INDICATOR_LABELS,
    MODERATE_FROM,
    IndicatorReading,
    PressureReading,
    Ranker,
    place_codes,
)

EVEN_MONTH_SHARE = 1 / 12
PEERS_SHOWN = 10

LIMITS = (
    "The pressure score is relative: it says where a destination sits among European "
    "regions on four official indicators. It is not a carrying-capacity threshold, and "
    "no official source defines one.",
    "Regional indicators are annual and are published with a delay; each figure states "
    "its year. Indicators can come from different years and from different NUTS levels.",
    "Short-term rental share is approximate: some platform-listed properties are also "
    "counted in official accommodation statistics.",
    "The outlook is a seasonal range, not a claim to beat last year's figure. In the "
    "pre-registered backtest it did so in 20 of 30 countries.",
)


@dataclass
class NationalRank:
    indicator: str
    label: str
    rank: int  # 1 = highest in the country
    regions: int
    year: int


@dataclass
class PeerRow:
    nuts_code: str
    name: str | None
    score: float
    level: str
    is_subject: bool
    rank: int  # within the country, 1 = highest pressure


@dataclass
class Trend:
    indicator: str
    label: str
    unit: str
    points: list[tuple[int, float]]
    change: float | None  # relative change, first to last year


@dataclass
class MonthShare:
    month: int
    share: float


@dataclass
class Seasonality:
    period: str  # e.g. "2025-07 to 2026-06"
    months: list[MonthShare]
    peak_month: int
    peak_share: float
    top3_share: float
    source: str


@dataclass
class Brief:
    place_id: int
    place_name: str
    place_type: str
    country_code: str | None
    generated_on: date
    pressure: PressureReading | None
    european_rank: int | None = None
    european_regions: int | None = None
    national: list[NationalRank] = field(default_factory=list)
    peers: list[PeerRow] = field(default_factory=list)
    trends: list[Trend] = field(default_factory=list)
    seasonality: Seasonality | None = None
    outlook: dict | None = None
    findings: list[str] = field(default_factory=list)
    sources: list[SourceLicence] = field(default_factory=list)
    withheld: list[str] = field(default_factory=list)
    limits: tuple[str, ...] = LIMITS


def format_value(reading_unit: str, value: float) -> str:
    if reading_unit.startswith("share"):
        return f"{value * 100:.1f}%"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:,.1f}"


def _ordinal_of(rank: int, total: int) -> str:
    return f"{rank} of {total}"


def _europe(ranker: Ranker, pressure: PressureReading) -> tuple[int, int, list[tuple[str, float]]]:
    """The subject's rank by score among all regions at its level, and
    every such region's score."""
    scores = []
    for code in ranker.codes_like(pressure.nuts_code):
        reading = ranker.pressure_for_codes([code])
        if reading.score is not None:
            scores.append((code, reading.score))
    higher = sum(score > (pressure.score or 0.0) for _, score in scores)
    return higher + 1, len(scores), scores


def _peers(
    ranker: Ranker, pressure: PressureReading, scores: list[tuple[str, float]]
) -> list[PeerRow]:
    """The country's regions at the same level, highest pressure first:
    the top of the table, always including the subject."""
    country = pressure.nuts_code[:2]
    national = sorted(
        ((code, score) for code, score in scores if code[:2] == country),
        key=lambda item: (-item[1], item[0]),
    )
    rows = [
        PeerRow(
            nuts_code=code,
            name=ranker.pressure_for_codes([code]).region_name,
            score=score,
            level="high" if score >= HIGH_FROM else "moderate" if score >= MODERATE_FROM else "low",
            is_subject=code == pressure.nuts_code,
            rank=position,
        )
        for position, (code, score) in enumerate(national, start=1)
    ]
    shown = rows[:PEERS_SHOWN]
    if not any(row.is_subject for row in shown):
        shown = shown[: PEERS_SHOWN - 1] + [row for row in rows if row.is_subject]
    return shown


def _national(ranker: Ranker, reading: IndicatorReading) -> NationalRank | None:
    """Rank within the country on one indicator, among regions at the
    same level reporting the same year."""
    values = []
    for code in ranker.codes_like(reading.region_code):
        if code[:2] != reading.region_code[:2]:
            continue
        year_values = dict(ranker.history(code, reading.indicator))
        if reading.year in year_values:
            values.append(year_values[reading.year])
    if len(values) < 2:
        return None
    return NationalRank(
        indicator=reading.indicator,
        label=reading.label,
        rank=sum(value > reading.value for value in values) + 1,
        regions=len(values),
        year=reading.year,
    )


def _trend(ranker: Ranker, reading: IndicatorReading) -> Trend | None:
    points = ranker.history(reading.region_code, reading.indicator)
    if len(points) < 2:
        return None
    first, last = points[0][1], points[-1][1]
    return Trend(
        indicator=reading.indicator,
        label=reading.label,
        unit=reading.unit,
        points=points,
        change=(last / first - 1) if first > 0 else None,
    )


def _nights_sources(db: Session, place_id: int) -> set[str]:
    rows = (
        db.query(Signal.source)
        .filter(Signal.place_id == place_id, Signal.signal_type == SIGNAL_TYPE)
        .distinct()
    )
    return {source for (source,) in rows}


def _seasonality(db: Session, place: Place, sources: set[str]) -> Seasonality | None:
    series = nights_by_place(db, [place.id]).get(place.id)
    if series is None:
        return None
    series = series.dropna().sort_index()
    if len(series) < 12:
        return None
    last = series.iloc[-12:]
    # Twelve consecutive months, or the shares are not shares of a year.
    if (last.index[-1] - last.index[0]).n != 11 or last.sum() <= 0:
        return None
    shares = (last / last.sum()).tolist()
    months = [
        MonthShare(period.month, share) for period, share in zip(last.index, shares, strict=True)
    ]
    peak = max(months, key=lambda item: item.share)
    return Seasonality(
        period=f"{last.index[0]} to {last.index[-1]}",
        months=sorted(months, key=lambda item: item.month),
        peak_month=peak.month,
        peak_share=peak.share,
        top3_share=sum(sorted(shares, reverse=True)[:3]),
        source=", ".join(licence_for(source).title for source in sorted(sources)),
    )


def _outlook_sources(outlook: dict, nights_sources: set[str]) -> set[str]:
    """The nights the model was fitted on, plus the attention series its
    name says it used (forecasting.service.POOLS)."""
    sources = set(nights_sources)
    suffix = outlook["model"].removeprefix("POOL_GR")
    if "W" in suffix:
        sources.add("wikipedia")
    if "G" in suffix:
        sources.add("gdelt")
    return sources


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _findings(brief: Brief) -> list[str]:
    out: list[str] = []
    pressure = brief.pressure
    if pressure is not None and pressure.score is not None:
        region = pressure.region_name or pressure.nuts_code
        sentence = (
            f"{region} scores {pressure.score:.0f} out of 100 for tourism pressure, "
            f"which is {pressure.level}"
        )
        if brief.european_rank and brief.european_regions:
            sentence += (
                f": rank {_ordinal_of(brief.european_rank, brief.european_regions)} "
                f"among European regions at {pressure.level_name} level"
            )
        out.append(sentence + ".")

        strongest = max(pressure.indicators, key=lambda reading: reading.percentile)
        out.append(
            f"The strongest pressure is on {strongest.label.lower()}: "
            f"{format_value(strongest.unit, strongest.value)} in {strongest.year}, higher than "
            f"{strongest.percentile:.0f}% of comparable European regions."
        )
        weakest = min(pressure.indicators, key=lambda reading: reading.percentile)
        if weakest is not strongest and strongest.percentile - weakest.percentile >= 25:
            out.append(
                f"It is not uniform: {weakest.label.lower()} sits at the "
                f"{weakest.percentile:.0f}th percentile, so the pressure is specific rather "
                f"than general."
            )

        by_name = {reading.indicator: reading for reading in pressure.indicators}
        rentals = by_name.get("str_share")
        if rentals is not None:
            out.append(
                f"Short-term rentals account for about {rentals.value * 100:.0f}% of recorded "
                f"nights ({rentals.year}), more than in {rentals.percentile:.0f}% of comparable "
                f"regions. Accommodation counts based on hotel beds alone leave this out."
            )
        for reading in pressure.dependence:
            if reading.percentile >= HIGH_FROM:
                out.append(
                    f"The local economy leans on visitor-facing sectors: "
                    f"{reading.label.lower()} is {format_value(reading.unit, reading.value)} "
                    f"({reading.year}), above {reading.percentile:.0f}% of comparable regions. "
                    f"Measures that reduce visitor numbers carry an economic cost here."
                )
                break

    season = brief.seasonality
    if season is not None:
        out.append(
            f"{MONTHS[season.peak_month - 1]} alone carries {season.peak_share * 100:.0f}% of "
            f"the year's nights and the three busiest months carry "
            f"{season.top3_share * 100:.0f}% ({season.period}). An even spread would be "
            f"{EVEN_MONTH_SHARE * 100:.0f}% a month."
        )

    year_ahead = next(
        (item for item in (brief.outlook or {}).get("outlook", []) if item["months"] == 12), None
    )
    if year_ahead is not None:
        low = year_ahead["low_80"] / year_ahead["last_year"] - 1
        high = year_ahead["high_80"] / year_ahead["last_year"] - 1
        out.append(
            f"The next twelve months are expected to bring {year_ahead['change'] * 100:+.1f}% "
            f"nights against the same months a year earlier, within a range of "
            f"{low * 100:+.0f}% to {high * 100:+.0f}%."
            + ("" if brief.outlook["validated"] else " This level is not yet validated.")
        )
    return out


def build_brief(db: Session, place: Place, today: date | None = None) -> Brief:
    brief = Brief(
        place_id=place.id,
        place_name=place.name,
        place_type=place.place_type,
        country_code=place.destination.country_code if place.destination else None,
        generated_on=today or date.today(),
        pressure=None,
    )
    used: set[str] = set()

    codes = place_codes(place)
    if codes:
        ranker = Ranker(db)
        pressure = ranker.pressure_for_codes(codes)
        readings = pressure.indicators + pressure.dependence
        blocked = not_cleared({reading.source for reading in readings})
        if blocked:
            brief.withheld.append(f"Pressure indicators (source not cleared: {', '.join(blocked)})")
        elif pressure.score is not None:
            brief.pressure = pressure
            used |= {reading.source for reading in readings}
            brief.european_rank, brief.european_regions, scores = _europe(ranker, pressure)
            brief.peers = _peers(ranker, pressure, scores)
            brief.national = [
                rank
                for reading in pressure.indicators
                if (rank := _national(ranker, reading)) is not None
            ]
            brief.trends = [
                trend for reading in readings if (trend := _trend(ranker, reading)) is not None
            ]

    nights_sources = _nights_sources(db, place.id)
    if nights_sources:
        blocked = not_cleared(nights_sources)
        if blocked:
            brief.withheld.append(f"Seasonality (source not cleared: {', '.join(blocked)})")
        else:
            brief.seasonality = _seasonality(db, place, nights_sources)
            if brief.seasonality is not None:
                used |= nights_sources

    outlook = place_forecast(db, place)
    if outlook is not None:
        outlook_sources = _outlook_sources(outlook, nights_sources)
        blocked = not_cleared(outlook_sources)
        if blocked:
            brief.withheld.append(f"12-month outlook (source not cleared: {', '.join(blocked)})")
        else:
            brief.outlook = outlook
            used |= outlook_sources

    brief.findings = _findings(brief)
    brief.sources = [licence_for(source) for source in sorted(used)]
    return brief


def find_place(db: Session, name: str) -> Place | None:
    """Exact name first, then a case-insensitive match; countries and
    regions before finer places when a name is shared."""
    order = {"country": 0, "region": 1}
    matches = db.query(Place).filter(Place.name.ilike(name)).all()
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda place: (place.name != name, order.get(place.place_type, 2), place.id),
    )[0]


__all__ = [
    "DEPENDENCE_LABELS",
    "INDICATOR_LABELS",
    "Brief",
    "build_brief",
    "find_place",
    "format_value",
]
