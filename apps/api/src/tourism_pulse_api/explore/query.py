"""Run a combined query: several catalog metrics on one place x time grid.

The result is long format - one row per (metric, place, period) - which
is what lets metrics from different sources sit side by side: a chart can
put two of them on a scatter's axes (joined on place), overlay them on a
time axis (joined on period), or pivot them into a table.

Every metric id is looked up in the catalog first; unknown ids raise, so
no user- or LLM-supplied text ever reaches SQL except as bound values.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import Date, case, cast, func
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import (
    Event,
    NewsArticle,
    Place,
    PlaceDemographics,
    PulseSnapshot,
    RegionalIndicator,
    Signal,
    VideoItem,
)
from tourism_pulse_api.explore.catalog import (
    COUNT,
    INDICATOR,
    POPULATION,
    SIGNAL,
    SNAPSHOT,
    STATIC,
    Metric,
    build_catalog,
)
from tourism_pulse_api.observatory.pressure import PeerCache, place_codes, pressure_for_place

GRAINS = ("day", "month", "year")
MAX_METRICS = 4
MAX_ROWS = 20_000

# Units normalised on the way out, so one metric has one unit everywhere.
_UNIT_FACTORS = {"thousand_nights": 1000.0}

_COUNT_TABLES = {
    "events": (Event, Event.start_at),
    "news_articles": (NewsArticle, NewsArticle.published_at),
    "video_items": (VideoItem, VideoItem.published_at),
}


class UnknownMetricError(ValueError):
    pass


@dataclass(frozen=True)
class QueryRow:
    metric: str
    place_id: int
    period: date | None
    value: float


@dataclass(frozen=True)
class QueryResult:
    metrics: list[Metric]
    places: list[Place]
    rows: list[QueryRow]
    truncated: bool
    # Plain-language caveats, e.g. incomplete periods left out.
    notes: list[str] = field(default_factory=list)


# How many native periods make one complete bucket, for summed metrics:
# a yearly sum of a monthly series is only meaningful with all 12 months.
_PERIODS_PER_BUCKET = {("month", "year"): 12}


def _bucket(column, grain: str):
    return cast(func.date_trunc(grain, column), Date)


def _in_range(period: date | None, start: date | None, end: date | None) -> bool:
    if period is None:
        return True
    return (start is None or period >= start) and (end is None or period <= end)


def _snapshot_rows(db: Session, metric: Metric, place_ids: list[int], grain: str):
    column = getattr(PulseSnapshot, metric.key)
    period = _bucket(PulseSnapshot.calculated_at, grain)
    query = (
        db.query(PulseSnapshot.place_id, period, func.avg(column))
        .filter(PulseSnapshot.place_id.in_(place_ids), column.isnot(None))
        .group_by(PulseSnapshot.place_id, period)
    )
    return query.all()


def _signal_rows(db: Session, metric: Metric, place_ids: list[int], grain: str, notes: list[str]):
    factor = case(
        *((Signal.unit == unit, factor) for unit, factor in _UNIT_FACTORS.items()),
        else_=1.0,
    )
    # One value per place and observation time first (averaging sources
    # that report the same moment), so summing into buckets never double
    # counts a month two sources both published.
    per_observation = (
        db.query(
            Signal.place_id.label("place_id"),
            Signal.observed_at.label("observed_at"),
            func.avg(Signal.value * factor).label("value"),
        )
        .filter(Signal.signal_type == metric.key, Signal.place_id.in_(place_ids))
        .group_by(Signal.place_id, Signal.observed_at)
        .subquery()
    )
    period = _bucket(per_observation.c.observed_at, grain)
    fold = func.sum if metric.aggregation == "sum" else func.avg
    native_periods = func.count(
        func.distinct(func.date_trunc(metric.grain, per_observation.c.observed_at))
    )
    rows = (
        db.query(per_observation.c.place_id, period, fold(per_observation.c.value), native_periods)
        .group_by(per_observation.c.place_id, period)
        .all()
    )

    required = _PERIODS_PER_BUCKET.get((metric.grain, grain))
    if metric.aggregation != "sum" or required is None:
        return [(place_id, bucket, value) for place_id, bucket, value, _n in rows]

    # A sum over a partial year (one stored month, or the current year so
    # far) would look like a real annual total. Leave it out and say so.
    complete = [(place_id, bucket, value) for place_id, bucket, value, n in rows if n >= required]
    dropped = len(rows) - len(complete)
    if dropped:
        notes.append(
            f"{metric.label}: {dropped} place-year(s) with fewer than {required} months "
            "left out, since a partial sum would read as an annual total."
        )
    return complete


def _indicator_rows(db: Session, metric: Metric, places: list[Place]):
    codes_by_place = {place.id: place_codes(place) for place in places}
    all_codes = {code for codes in codes_by_place.values() for code in codes}
    if not all_codes:
        return []
    values: dict[str, list[tuple[int, float]]] = {}
    for code, year, value in db.query(
        RegionalIndicator.nuts_code, RegionalIndicator.year, RegionalIndicator.value
    ).filter(RegionalIndicator.indicator == metric.key, RegionalIndicator.nuts_code.in_(all_codes)):
        values.setdefault(code, []).append((year, value))

    rows = []
    for place_id, codes in codes_by_place.items():
        # The finest region that has this indicator at all.
        code = next((code for code in codes if code in values), None)
        if code is None:
            continue
        rows.extend((place_id, date(year, 1, 1), value) for year, value in values[code])
    return rows


def _population_rows(db: Session, place_ids: list[int]):
    return [
        (place_id, date(year, 1, 1), float(population))
        for place_id, year, population in db.query(
            PlaceDemographics.place_id, PlaceDemographics.year, PlaceDemographics.population
        ).filter(PlaceDemographics.place_id.in_(place_ids))
    ]


def _count_rows(db: Session, metric: Metric, place_ids: list[int], grain: str):
    model, timestamp = _COUNT_TABLES[metric.key]
    period = _bucket(timestamp, grain)
    return (
        db.query(model.place_id, period, func.count())
        .filter(model.place_id.in_(place_ids), timestamp.isnot(None))
        .group_by(model.place_id, period)
        .all()
    )


def _static_rows(db: Session, metric: Metric, places: list[Place]):
    cache = PeerCache()
    rows = []
    for place in places:
        reading = pressure_for_place(db, place, cache)
        if reading is not None and reading.score is not None:
            rows.append((place.id, None, reading.score))
    return rows


def _metric_rows(
    db: Session, metric: Metric, places: list[Place], grain: str, notes: list[str]
) -> Iterable[tuple[int, date | None, float]]:
    place_ids = [place.id for place in places]
    if metric.kind == SNAPSHOT:
        return _snapshot_rows(db, metric, place_ids, grain)
    if metric.kind == SIGNAL:
        return _signal_rows(db, metric, place_ids, grain, notes)
    if metric.kind == INDICATOR:
        return _indicator_rows(db, metric, places)
    if metric.kind == POPULATION:
        return _population_rows(db, place_ids)
    if metric.kind == COUNT:
        return _count_rows(db, metric, place_ids, grain)
    if metric.kind == STATIC:
        return _static_rows(db, metric, places)
    raise UnknownMetricError(f"Unsupported metric kind {metric.kind!r}")


def resolve_places(db: Session, place_ids: list[int] | None, place_type: str | None) -> list[Place]:
    query = db.query(Place)
    if place_ids:
        query = query.filter(Place.id.in_(place_ids))
    if place_type == "country":
        query = query.filter(Place.place_type == "country")
    elif place_type == "destination":
        query = query.filter(Place.place_type != "country")
    return query.order_by(Place.name).all()


def run_query(
    db: Session,
    *,
    metric_ids: list[str],
    place_ids: list[int] | None = None,
    place_type: str | None = None,
    grain: str = "month",
    start: date | None = None,
    end: date | None = None,
) -> QueryResult:
    if not metric_ids:
        raise UnknownMetricError("Pick at least one metric")
    if len(metric_ids) > MAX_METRICS:
        raise UnknownMetricError(f"At most {MAX_METRICS} metrics can be combined")
    if grain not in GRAINS:
        raise UnknownMetricError(f"Grain must be one of {', '.join(GRAINS)}")

    catalog = build_catalog(db)
    unknown = [metric_id for metric_id in metric_ids if metric_id not in catalog]
    if unknown:
        raise UnknownMetricError(f"Unknown metric(s): {', '.join(unknown)}")
    metrics = [catalog[metric_id] for metric_id in dict.fromkeys(metric_ids)]

    places = resolve_places(db, place_ids, place_type)
    rows: list[QueryRow] = []
    notes: list[str] = []
    truncated = False
    for metric in metrics:
        for place_id, period, value in _metric_rows(db, metric, places, grain, notes):
            if value is None or not _in_range(period, start, end):
                continue
            if len(rows) >= MAX_ROWS:
                truncated = True
                break
            rows.append(QueryRow(metric.id, place_id, period, round(float(value), 6)))

    rows.sort(key=lambda row: (row.metric, row.place_id, row.period or date.min))
    return QueryResult(metrics=metrics, places=places, rows=rows, truncated=truncated, notes=notes)
