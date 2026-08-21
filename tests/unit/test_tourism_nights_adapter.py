from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.tourism_nights_adapter import (
    process_tourism_nights_signal,
)


def make_signal(
    id: int,
    value: float,
    observed_at: datetime,
    *,
    signal_type: str = "tourism_nights",
    source: str = "ksh",
) -> Signal:
    return Signal(
        id=id,
        place_id=61,
        signal_type=signal_type,
        value=Decimal(str(value)),
        unit="thousand_nights",
        observed_at=observed_at,
        source=source,
    )


def test_maps_to_demand_dimension_with_enough_history() -> None:
    history = [
        make_signal(1, 100, datetime(2021, 6, 30, tzinfo=UTC)),
        make_signal(2, 110, datetime(2022, 6, 30, tzinfo=UTC)),
        make_signal(3, 120, datetime(2023, 6, 30, tzinfo=UTC)),
    ]
    target = make_signal(4, 150, datetime(2024, 6, 30, tzinfo=UTC))

    result = process_tourism_nights_signal(
        target,
        history=[*history, target],
        now=datetime(2024, 7, 1, tzinfo=UTC),
    )

    assert result is not None
    assert result.dimension == "demand"
    assert 0.0 <= result.normalized_value <= 1.0
    assert result.source == "ksh"
    assert result.half_life_hours == 720.0


def test_returns_none_when_history_is_insufficient() -> None:
    target = make_signal(1, 150, datetime(2021, 6, 30, tzinfo=UTC))

    result = process_tourism_nights_signal(target, history=[target])

    assert result is None


def test_ignores_other_calendar_months_when_building_history() -> None:
    history = [
        make_signal(1, 999, datetime(2023, 1, 31, tzinfo=UTC)),
        make_signal(2, 100, datetime(2022, 6, 30, tzinfo=UTC)),
        make_signal(3, 110, datetime(2023, 6, 30, tzinfo=UTC)),
    ]
    target = make_signal(4, 150, datetime(2024, 6, 30, tzinfo=UTC))

    result = process_tourism_nights_signal(target, history=[*history, target])

    assert result is not None


def test_excludes_future_observations_from_the_baseline() -> None:
    target = make_signal(1, 100, datetime(2022, 6, 30, tzinfo=UTC))
    future_one = make_signal(2, 999, datetime(2023, 6, 30, tzinfo=UTC))
    future_two = make_signal(3, 999, datetime(2024, 6, 30, tzinfo=UTC))

    result = process_tourism_nights_signal(
        target,
        history=[target, future_one, future_two],
    )

    assert result is None  # no *prior* same-month history exists


def test_excludes_itself_from_its_own_baseline() -> None:
    target = make_signal(1, 100, datetime(2024, 6, 30, tzinfo=UTC))

    result = process_tourism_nights_signal(target, history=[target])

    assert result is None


def test_rejects_wrong_signal_type() -> None:
    signal = make_signal(
        1,
        100,
        datetime(2022, 6, 30, tzinfo=UTC),
        signal_type="occupancy",
    )

    with pytest.raises(ValueError):
        process_tourism_nights_signal(signal, history=[signal])
