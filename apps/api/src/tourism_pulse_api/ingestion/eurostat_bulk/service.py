"""Map Eurostat codes to places and bulk-upsert signals and population."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.checks import IMPOSSIBLE_RANGE_BOUNDS
from tourism_pulse_api.db.models import Place, PlaceDemographics, Signal, SignalBreakdown
from tourism_pulse_api.ingestion.eurostat_bulk.parser import (
    AREA,
    CITY,
    COUNTRY,
    EUROSTAT_SOURCE_NAME,
    REGION,
    Record,
)

_BATCH_ROWS = 1000


@dataclass
class LoadSummary:
    written: int = 0
    invalid: int = 0
    unmatched_codes: set[str] = field(default_factory=set)
    places: set[int] = field(default_factory=set)


def place_index(db: Session) -> dict[str, dict[str, list[int]]]:
    """kind -> Eurostat code -> place ids. Each code maps within one kind
    only, so e.g. the NUTS 2 code HU11 reaches the region place, never the
    curated Budapest destination that also carries it."""
    index: dict[str, dict[str, list[int]]] = {
        kind: defaultdict(list) for kind in (COUNTRY, REGION, AREA, CITY)
    }
    for place in db.query(Place):
        if place.place_type == "country" and place.nuts_code:
            index[COUNTRY][place.nuts_code].append(place.id)
        elif place.place_type == "region" and place.nuts_code:
            index[REGION][place.nuts_code].append(place.id)
        elif place.place_type == "area" and place.nuts3_code:
            index[AREA][place.nuts3_code].append(place.id)
        if place.urau_code:
            index[CITY][place.urau_code].append(place.id)
    return index


def _targets(index, kinds: tuple[str, ...], code: str) -> list[int]:
    for kind in kinds:
        ids = index[kind].get(code)
        if ids:
            return ids
    return []


def _valid(record: Record) -> bool:
    low, high = IMPOSSIBLE_RANGE_BOUNDS.get(record.signal_type, (0.0, None))
    return record.value >= low and (high is None or record.value <= high)


def upsert_signals(
    db: Session,
    records: list[Record],
    *,
    kinds: tuple[str, ...],
    source_url: str,
    source_observation_id: int | None,
    index: dict[str, dict[str, list[int]]],
) -> LoadSummary:
    summary = LoadSummary()
    rows: dict[tuple, dict] = {}
    for record in records:
        place_ids = _targets(index, kinds, record.code)
        if not place_ids:
            summary.unmatched_codes.add(record.code)
            continue
        if not _valid(record):
            summary.invalid += 1
            continue
        for place_id in place_ids:
            key = (place_id, record.signal_type, record.observed_at)
            rows[key] = {
                "place_id": place_id,
                "signal_type": record.signal_type,
                "value": record.value,
                "unit": record.unit,
                "observed_at": record.observed_at,
                "source": EUROSTAT_SOURCE_NAME,
                "source_url": source_url,
                "source_observation_id": source_observation_id,
            }
            summary.places.add(place_id)

    values = list(rows.values())
    for start in range(0, len(values), _BATCH_ROWS):
        statement = insert(Signal).values(values[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            constraint="uq_signals_place_type_observed_source",
            set_={
                "value": statement.excluded.value,
                "unit": statement.excluded.unit,
                "source_url": statement.excluded.source_url,
                "source_observation_id": statement.excluded.source_observation_id,
            },
        )
        db.execute(statement)
    db.commit()
    summary.written = len(values)
    return summary


def upsert_breakdowns(
    db: Session,
    records: list[Record],
    *,
    kinds: tuple[str, ...],
    dimension: str,
    index: dict[str, dict[str, list[int]]],
) -> LoadSummary:
    """Parts of a stored signal (records with a key), e.g. a country's
    annual nights by the guests' country of residence."""
    summary = LoadSummary()
    rows: dict[tuple, dict] = {}
    for record in records:
        place_ids = _targets(index, kinds, record.code)
        if not place_ids:
            summary.unmatched_codes.add(record.code)
            continue
        if record.key is None or not _valid(record):
            summary.invalid += 1
            continue
        for place_id in place_ids:
            rows[(place_id, record.signal_type, record.observed_at, record.key)] = {
                "place_id": place_id,
                "signal_type": record.signal_type,
                "observed_at": record.observed_at,
                "dimension": dimension,
                "key": record.key,
                "value": record.value,
                "source": EUROSTAT_SOURCE_NAME,
            }
            summary.places.add(place_id)
    values = list(rows.values())
    for start in range(0, len(values), _BATCH_ROWS):
        statement = insert(SignalBreakdown).values(values[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            constraint="uq_signal_breakdowns_place_type_observed_dimension_key",
            set_={"value": statement.excluded.value},
        )
        db.execute(statement)
    db.commit()
    summary.written = len(values)
    return summary


def upsert_population(
    db: Session,
    records: list[Record],
    *,
    source_observation_id: int | None,
    index: dict[str, dict[str, list[int]]],
) -> LoadSummary:
    summary = LoadSummary()
    rows: dict[tuple, dict] = {}
    retrieved_at = datetime.now(UTC)
    for record in records:
        place_ids = _targets(index, (COUNTRY, REGION, AREA), record.code)
        if not place_ids:
            summary.unmatched_codes.add(record.code)
            continue
        for place_id in place_ids:
            rows[(place_id, record.observed_at.year)] = {
                "place_id": place_id,
                "year": record.observed_at.year,
                "population": int(record.value),
                "source": EUROSTAT_SOURCE_NAME,
                "source_observation_id": source_observation_id,
                "retrieved_at": retrieved_at,
            }
            summary.places.add(place_id)
    values = list(rows.values())
    for start in range(0, len(values), _BATCH_ROWS):
        statement = insert(PlaceDemographics).values(values[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            index_elements=["place_id", "year"],
            set_={
                "population": statement.excluded.population,
                "source_observation_id": statement.excluded.source_observation_id,
                "retrieved_at": statement.excluded.retrieved_at,
            },
        )
        db.execute(statement)
    db.commit()
    summary.written = len(values)
    return summary
