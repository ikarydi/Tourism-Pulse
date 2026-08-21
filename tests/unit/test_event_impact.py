from datetime import datetime, timezone

import pytest

from tourism_pulse_api.pulse.event_impact import calculate_event_impact


NOW = datetime(
    2026,
    8,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def test_active_festival_has_full_impact() -> None:
    result = calculate_event_impact(
        event_type="festival",
        start_at=datetime(
            2026, 8, 20, 10, 0, tzinfo=timezone.utc
        ),
        end_at=datetime(
            2026, 8, 20, 20, 0, tzinfo=timezone.utc
        ),
        now=NOW,
    )

    assert result == pytest.approx(1.0)


def test_event_starting_within_24_hours_has_high_impact() -> None:
    result = calculate_event_impact(
        event_type="concert",
        start_at=datetime(
            2026, 8, 20, 20, 0, tzinfo=timezone.utc
        ),
        now=NOW,
    )

    assert result == pytest.approx(0.675)


def test_event_starting_within_three_days_has_medium_impact() -> None:
    result = calculate_event_impact(
        event_type="conference",
        start_at=datetime(
            2026, 8, 22, 12, 0, tzinfo=timezone.utc
        ),
        now=NOW,
    )

    assert result == pytest.approx(0.40)


def test_event_starting_within_week_has_low_impact() -> None:
    result = calculate_event_impact(
        event_type="cultural",
        start_at=datetime(
            2026, 8, 26, 12, 0, tzinfo=timezone.utc
        ),
        now=NOW,
    )

    assert result == pytest.approx(0.20)


def test_distant_event_has_no_impact() -> None:
    result = calculate_event_impact(
        event_type="festival",
        start_at=datetime(
            2026, 9, 20, 12, 0, tzinfo=timezone.utc
        ),
        now=NOW,
    )

    assert result == 0.0


def test_unknown_event_type_uses_other_weight() -> None:
    result = calculate_event_impact(
        event_type="something_new",
        start_at=datetime(
            2026, 8, 20, 12, 0, tzinfo=timezone.utc
        ),
        end_at=datetime(
            2026, 8, 20, 18, 0, tzinfo=timezone.utc
        ),
        now=NOW,
    )

    assert result == pytest.approx(0.50)


def test_invalid_event_range_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_event_impact(
            event_type="festival",
            start_at=datetime(
                2026, 8, 20, 20, 0, tzinfo=timezone.utc
            ),
            end_at=datetime(
                2026, 8, 20, 10, 0, tzinfo=timezone.utc
            ),
            now=NOW,
        )
