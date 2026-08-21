from datetime import datetime, timezone

from tourism_pulse_api.db.models.pulse_snapshot import PulseSnapshot
from tourism_pulse_api.pulse.trend_analysis import analyze_trend


def make_snapshot(
    pulse: float,
    demand: float = 50,
    capacity: float = 50,
    events: float = 50,
    environment: float = 50,
) -> PulseSnapshot:
    return PulseSnapshot(
        place_id=1,
        calculated_at=datetime.now(timezone.utc),
        pulse=pulse,
        demand=demand,
        capacity=capacity,
        events=events,
        environment=environment,
        confidence_score=80,
        confidence_coverage=100,
    )


def test_upward_trend() -> None:
    current = make_snapshot(65)
    previous = make_snapshot(55)

    result = analyze_trend(
        current=current,
        previous_24h=previous,
        previous_7d=previous,
    )

    assert result.change_24h == 10
    assert result.direction == "up"
    assert result.momentum == "strong"


def test_downward_trend() -> None:
    current = make_snapshot(40)
    previous = make_snapshot(50)

    result = analyze_trend(
        current=current,
        previous_24h=previous,
        previous_7d=previous,
    )

    assert result.change_24h == -10
    assert result.direction == "down"
    assert result.momentum == "strong"


def test_insufficient_history() -> None:
    current = make_snapshot(50)

    result = analyze_trend(
        current=current,
        previous_24h=None,
        previous_7d=None,
    )

    assert result.change_24h is None
    assert result.change_7d is None
    assert result.direction == "insufficient_data"
    assert result.momentum == "unknown"


def test_dimension_drivers() -> None:
    current = make_snapshot(
        65,
        demand=70,
        capacity=45,
        events=80,
        environment=40,
    )

    previous = make_snapshot(
        55,
        demand=60,
        capacity=55,
        events=70,
        environment=50,
    )

    result = analyze_trend(
        current=current,
        previous_24h=previous,
        previous_7d=previous,
    )

    assert "Demand improved" in result.positive_drivers
    assert "Events improved" in result.positive_drivers
    assert "Capacity weakened" in result.negative_drivers
    assert "Environment weakened" in result.negative_drivers
