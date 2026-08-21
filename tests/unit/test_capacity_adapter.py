from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.capacity_adapter import process_capacity_signal


def make_signal(
    id: int,
    value: float,
    observed_at: datetime,
    *,
    signal_type: str = "accommodation_capacity",
    source: str = "ksh",
) -> Signal:
    return Signal(
        id=id,
        place_id=347,
        signal_type=signal_type,
        value=Decimal(str(value)),
        unit="beds",
        observed_at=observed_at,
        source=source,
    )


def test_maps_to_capacity_dimension_with_enough_history() -> None:
    history = [
        make_signal(1, 400000, datetime(2021, 6, 30, tzinfo=UTC)),
        make_signal(2, 420000, datetime(2022, 6, 30, tzinfo=UTC)),
        make_signal(3, 440000, datetime(2023, 6, 30, tzinfo=UTC)),
    ]
    target = make_signal(4, 500000, datetime(2024, 6, 30, tzinfo=UTC))

    result = process_capacity_signal(
        target,
        history=[*history, target],
        now=datetime(2024, 7, 1, tzinfo=UTC),
    )

    assert result is not None
    assert result.dimension == "capacity"
    assert 0.0 <= result.normalized_value <= 1.0
    assert result.source == "ksh"
    assert result.half_life_hours == 720.0


def test_returns_none_when_history_is_insufficient() -> None:
    target = make_signal(1, 500000, datetime(2021, 6, 30, tzinfo=UTC))

    result = process_capacity_signal(target, history=[target])

    assert result is None


def test_rejects_wrong_signal_type() -> None:
    signal = make_signal(
        1,
        500000,
        datetime(2022, 6, 30, tzinfo=UTC),
        signal_type="tourism_nights",
    )

    with pytest.raises(ValueError):
        process_capacity_signal(signal, history=[signal])
