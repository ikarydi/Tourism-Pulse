from datetime import datetime, timezone

import pytest

from tourism_pulse_api.db.models.event import Event
from tourism_pulse_api.pulse.event_adapter import event_to_signal


NOW = datetime(
    2026,
    8,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def test_event_is_converted_to_events_signal() -> None:
    event = Event(
        place_id=1,
        name="Budapest Festival",
        event_type="festival",
        start_at=datetime(
            2026, 8, 20, 10, 0, tzinfo=timezone.utc
        ),
        end_at=datetime(
            2026, 8, 20, 20, 0, tzinfo=timezone.utc
        ),
    )

    result = event_to_signal(
        event,
        now=NOW,
    )

    assert result.dimension == "events"
    assert result.normalized_value == pytest.approx(1.0)
    assert result.age_hours == 0.0
    assert result.half_life_hours == 12.0
    assert result.source == "official"


def test_future_event_produces_reduced_signal() -> None:
    event = Event(
        place_id=1,
        name="Concert",
        event_type="concert",
        start_at=datetime(
            2026, 8, 20, 20, 0, tzinfo=timezone.utc
        ),
    )

    result = event_to_signal(
        event,
        now=NOW,
    )

    assert result.dimension == "events"
    assert result.normalized_value == pytest.approx(0.675)
