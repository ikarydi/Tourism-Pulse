from datetime import datetime, timezone

from tourism_pulse_api.db.models.pulse_snapshot import PulseSnapshot
from tourism_pulse_api.pulse.anomaly import detect_anomaly


def make_snapshot(
    pulse: float,
    confidence_score: float = 90,
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
        confidence_score=confidence_score,
        confidence_coverage=100,
    )


def test_no_anomaly_for_small_change() -> None:
    result = detect_anomaly(
        current=make_snapshot(53),
        previous=make_snapshot(50),
    )

    assert result.detected is False
    assert result.severity == "none"
    assert result.change == 3


def test_moderate_anomaly() -> None:
    result = detect_anomaly(
        current=make_snapshot(57),
        previous=make_snapshot(50),
    )

    assert result.detected is True
    assert result.severity == "moderate"
    assert result.change == 7


def test_high_anomaly() -> None:
    result = detect_anomaly(
        current=make_snapshot(62),
        previous=make_snapshot(50),
    )

    assert result.detected is True
    assert result.severity == "high"


def test_extreme_anomaly() -> None:
    result = detect_anomaly(
        current=make_snapshot(75),
        previous=make_snapshot(50),
    )

    assert result.detected is True
    assert result.severity == "extreme"


def test_low_confidence_limits_severity() -> None:
    result = detect_anomaly(
        current=make_snapshot(
            75,
            confidence_score=40,
        ),
        previous=make_snapshot(50),
    )

    assert result.detected is True
    assert result.severity == "low"


def test_insufficient_history() -> None:
    result = detect_anomaly(
        current=make_snapshot(50),
        previous=None,
    )

    assert result.detected is False
    assert result.severity == "none"
    assert result.change is None


def test_dimension_drivers() -> None:
    result = detect_anomaly(
        current=make_snapshot(
            65,
            demand=70,
            capacity=45,
            events=80,
            environment=40,
        ),
        previous=make_snapshot(
            50,
            demand=60,
            capacity=55,
            events=70,
            environment=50,
        ),
    )

    assert "Demand changed by +10.0" in result.drivers
    assert "Capacity changed by -10.0" in result.drivers
    assert "Events changed by +10.0" in result.drivers
    assert "Environment changed by -10.0" in result.drivers
