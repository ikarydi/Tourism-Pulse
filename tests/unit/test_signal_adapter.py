from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.signal_adapter import signal_to_input


def make_signal(
    signal_type: str = "demand",
) -> Signal:
    return Signal(
        id=1,
        place_id=1,
        signal_type=signal_type,
        value=Decimal("0.75"),
        unit="score",
        observed_at=datetime.now(UTC),
        source="government",
    )


def test_signal_to_input() -> None:
    signal = make_signal()

    result = signal_to_input(
        signal,
        normalized_value=0.75,
        age_hours=2.0,
        half_life_hours=24.0,
    )

    assert result.dimension == "demand"
    assert result.normalized_value == 0.75
    assert result.age_hours == 2.0
    assert result.half_life_hours == 24.0
    assert result.source == "government"


@pytest.mark.parametrize(
    ("signal_type", "expected_dimension"),
    [
        ("demand", "demand"),
        ("capacity", "capacity"),
        ("event", "events"),
        ("events", "events"),
        ("environment", "environment"),
        ("tourism_nights", "demand"),
        ("accommodation_capacity", "capacity"),
        ("occupancy_rate", "demand"),
    ],
)
def test_signal_type_mapping(
    signal_type: str,
    expected_dimension: str,
) -> None:
    signal = make_signal(signal_type)

    result = signal_to_input(
        signal,
        normalized_value=0.75,
        age_hours=0,
        half_life_hours=24,
    )

    assert result.dimension == expected_dimension


def test_signal_type_is_case_insensitive() -> None:
    signal = make_signal("DEMAND")

    result = signal_to_input(
        signal,
        normalized_value=0.75,
        age_hours=0,
        half_life_hours=24,
    )

    assert result.dimension == "demand"


def test_unknown_signal_type_rejected() -> None:
    signal = make_signal("something_unknown")

    with pytest.raises(ValueError):
        signal_to_input(
            signal,
            normalized_value=0.75,
            age_hours=0,
            half_life_hours=24,
        )
