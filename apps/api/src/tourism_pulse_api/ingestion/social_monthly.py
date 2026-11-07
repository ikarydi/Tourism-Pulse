"""Shared helpers for the monthly social media adapters (YouTube uploads,
Reddit and Bluesky).

Only aggregates leave these adapters: a count and a felt-pressure share
per place and month, with source and fetch time. Post text, usernames and
post ids are read in memory and never stored or archived, so nothing
personal is kept (GDPR) and nothing has to be deleted when a post is.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Signal, SignalBreakdown


def month_start(month: str) -> datetime:
    """'2026-10' -> 2026-10-01T00:00Z."""
    return datetime(int(month[:4]), int(month[5:7]), 1, tzinfo=UTC)


def next_month(month: str) -> str:
    year, number = int(month[:4]), int(month[5:7])
    return f"{year + (number == 12):04d}-{number % 12 + 1:02d}"


def month_end(month: str) -> datetime:
    """Last day of the month at 00:00 UTC: the observed_at convention of
    the other monthly series (see ingestion.wikipedia_monthly)."""
    following = month_start(next_month(month)).date()
    last = date.fromordinal(following.toordinal() - 1)
    return datetime(last.year, last.month, last.day, tzinfo=UTC)


def month_of(moment: datetime) -> str:
    return f"{moment.year:04d}-{moment.month:02d}"


def complete_months(start: str, today: date) -> list[str]:
    """Every month from `start` up to, not including, the current one."""
    current = f"{today.year:04d}-{today.month:02d}"
    months: list[str] = []
    month = start
    while month < current:
        months.append(month)
        month = next_month(month)
    return months


@dataclass(frozen=True)
class MonthlyValue:
    place_id: int
    signal_type: str
    month: str
    value: float
    unit: str


def upsert_monthly_signals(
    db: Session,
    values: list[MonthlyValue],
    *,
    source: str,
    source_url: str,
    source_observation_id: int | None,
) -> int:
    rows = [
        {
            "place_id": v.place_id,
            "signal_type": v.signal_type,
            "value": v.value,
            "unit": v.unit,
            "observed_at": month_end(v.month),
            "source": source,
            "source_url": source_url,
            "source_observation_id": source_observation_id,
        }
        for v in values
    ]
    for begin in range(0, len(rows), 1000):
        statement = insert(Signal).values(rows[begin : begin + 1000])
        statement = statement.on_conflict_do_update(
            constraint="uq_signals_place_type_observed_source",
            set_={
                "value": statement.excluded.value,
                "source_observation_id": statement.excluded.source_observation_id,
            },
        )
        db.execute(statement)
    return len(rows)


def upsert_language_breakdowns(
    db: Session,
    *,
    place_id: int,
    signal_type: str,
    month: str,
    counts: dict[str, int],
    source: str,
) -> int:
    rows = [
        {
            "place_id": place_id,
            "signal_type": signal_type,
            "observed_at": month_end(month),
            "dimension": "language",
            "key": language,
            "value": count,
            "source": source,
        }
        for language, count in counts.items()
    ]
    if rows:
        statement = insert(SignalBreakdown).values(rows)
        statement = statement.on_conflict_do_update(
            constraint="uq_signal_breakdowns_place_type_observed_dimension_key",
            set_={"value": statement.excluded.value},
        )
        db.execute(statement)
    return len(rows)
