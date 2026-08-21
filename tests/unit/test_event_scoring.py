from datetime import datetime, timezone

from tourism_pulse_api.db.models.event import Event
from tourism_pulse_api.pulse.event_scoring import calculate_event_score


NOW = datetime(
    2026,
    8,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_event(
    start_at: datetime,
    end_at: datetime | None = None,
) -> Event:
    return Event(
        place_id=1,
        name="Test Event",
        event_type="festival",
        start_at=start_at,
        end_at=end_at,
    )


def test_active_event_scores_one() -> None:
    event = make_event(
        start_at=datetime(
            2026, 8, 20, 10, 0, tzinfo=timezone.utc
        ),
        end_at=datetime(
            2026, 8, 20, 18, 0, tzinfo=timezone.utc
        ),
    )

    assert calculate_event_score(
        event,
        now=NOW,
    ) == 1.0


def test_event_within_24_hours_scores_point_eight() -> None:
    event = make_event(
        start_at=datetime(
            2026, 8, 21, 10, 0, tzinfo=timezone.utc
        ),
    )

    assert calculate_event_score(
        event,
        now=NOW,
    ) == 0.8


def test_event_within_72_hours_scores_point_five() -> None:
    event = make_event(
        start_at=datetime(
            2026, 8, 22, 12, 0, tzinfo=timezone.utc
        ),
    )

    assert calculate_event_score(
        event,
        now=NOW,
    ) == 0.5


def test_distant_event_scores_point_two() -> None:
    event = make_event(
        start_at=datetime(
            2026, 8, 30, 12, 0, tzinfo=timezone.utc
        ),
    )

    assert calculate_event_score(
        event,
        now=NOW,
    ) == 0.2


def test_finished_event_scores_zero() -> None:
    event = make_event(
        start_at=datetime(
            2026, 8, 19, 10, 0, tzinfo=timezone.utc
        ),
        end_at=datetime(
            2026, 8, 19, 18, 0, tzinfo=timezone.utc
        ),
    )

    assert calculate_event_score(
        event,
        now=NOW,
    ) == 0.0
