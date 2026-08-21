from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.seasonal_signal_adapter import (
    SEASONAL_SIGNAL_TYPES,
    process_seasonal_signal,
)


def make_signal(
    id: int,
    value: float,
    observed_at: datetime,
    *,
    signal_type: str,
    source: str = "ksh",
) -> Signal:
    return Signal(
        id=id,
        place_id=1,
        signal_type=signal_type,
        value=Decimal(str(value)),
        unit="thousand_nights",
        observed_at=observed_at,
        source=source,
    )


def test_seasonal_signal_types_registry_contains_both_ksh_types() -> None:
    assert SEASONAL_SIGNAL_TYPES == frozenset(
        {"tourism_nights", "accommodation_capacity", "accommodation_capacity_annual"}
    )


@pytest.mark.parametrize("signal_type", ["tourism_nights", "accommodation_capacity"])
def test_processes_each_registered_seasonal_type(signal_type: str) -> None:
    history = [
        make_signal(1, 100, datetime(2022, 6, 30, tzinfo=UTC), signal_type=signal_type),
        make_signal(2, 110, datetime(2023, 6, 30, tzinfo=UTC), signal_type=signal_type),
    ]
    target = make_signal(3, 150, datetime(2024, 6, 30, tzinfo=UTC), signal_type=signal_type)

    result = process_seasonal_signal(target, history=[*history, target])

    assert result is not None
    assert 0.0 <= result.normalized_value <= 1.0


def test_rejects_a_non_seasonal_signal_type() -> None:
    signal = make_signal(1, 100, datetime(2022, 6, 30, tzinfo=UTC), signal_type="occupancy")

    with pytest.raises(ValueError):
        process_seasonal_signal(signal, history=[signal])


def test_different_signal_types_do_not_leak_into_each_others_baseline() -> None:
    # Same place, same month, same years - but different signal_type. If the
    # capacity signal's history were built from mixed types, this June 2024
    # tourism_nights signal would see a "sufficient" baseline it shouldn't.
    capacity_type = "accommodation_capacity"
    capacity_history = [
        make_signal(1, 400000, datetime(2022, 6, 30, tzinfo=UTC), signal_type=capacity_type),
        make_signal(2, 420000, datetime(2023, 6, 30, tzinfo=UTC), signal_type=capacity_type),
    ]
    tourism_nights_target = make_signal(
        3, 1487, datetime(2024, 6, 30, tzinfo=UTC), signal_type="tourism_nights"
    )

    result = process_seasonal_signal(
        tourism_nights_target,
        history=[*capacity_history, tourism_nights_target],
    )

    assert result is None
