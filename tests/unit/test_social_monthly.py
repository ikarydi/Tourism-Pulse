from datetime import UTC, date, datetime

from tourism_pulse_api.ingestion.social_monthly import (
    complete_months,
    month_end,
    month_of,
    month_start,
    next_month,
)


def test_month_boundaries() -> None:
    assert month_start("2026-02") == datetime(2026, 2, 1, tzinfo=UTC)
    assert month_end("2026-02") == datetime(2026, 2, 28, tzinfo=UTC)
    assert month_end("2024-02") == datetime(2024, 2, 29, tzinfo=UTC)
    assert next_month("2026-12") == "2027-01"
    assert month_of(datetime(2026, 10, 31, 23, 59, tzinfo=UTC)) == "2026-10"


def test_complete_months_stop_before_the_current_month() -> None:
    assert complete_months("2026-09", date(2026, 11, 7)) == ["2026-09", "2026-10"]
    assert complete_months("2026-11", date(2026, 11, 7)) == []
