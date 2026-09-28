"""Upsert regional indicators, one row per (NUTS code, indicator, year)."""

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import RegionalIndicator
from tourism_pulse_api.ingestion.eurostat_regional.parser import (
    EUROSTAT_SOURCE_NAME,
    INDICATOR_UNITS,
    IndicatorValue,
)

_BATCH_ROWS = 1000


def upsert_indicators(
    db: Session,
    values: list[IndicatorValue],
    *,
    source_observation_id: int | None,
    retrieved_at: datetime | None = None,
) -> int:
    if not values:
        return 0
    retrieved_at = retrieved_at or datetime.now(UTC)
    rows = [
        {
            "nuts_code": value.nuts_code,
            "indicator": value.indicator,
            "year": value.year,
            "value": value.value,
            "unit": INDICATOR_UNITS[value.indicator],
            "source": EUROSTAT_SOURCE_NAME,
            "source_observation_id": source_observation_id,
            "retrieved_at": retrieved_at,
        }
        for value in values
    ]
    # Postgres caps one statement at 65,535 bind parameters (8 per row).
    for start in range(0, len(rows), _BATCH_ROWS):
        statement = insert(RegionalIndicator).values(rows[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            index_elements=["nuts_code", "indicator", "year"],
            set_={
                "value": statement.excluded.value,
                "unit": statement.excluded.unit,
                "source_observation_id": statement.excluded.source_observation_id,
                "retrieved_at": statement.excluded.retrieved_at,
            },
        )
        db.execute(statement)
    db.commit()
    return len(rows)
