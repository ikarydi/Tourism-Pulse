import pytest

from tourism_pulse_api.pulse.trend import calculate_trend


def test_positive_trend() -> None:
    result = calculate_trend(
        current_pulse=82.5,
        previous_pulse=75.0,
    )

    assert result.change == 7.5
    assert result.direction == "up"


def test_negative_trend() -> None:
    result = calculate_trend(
        current_pulse=68.0,
        previous_pulse=74.5,
    )

    assert result.change == -6.5
    assert result.direction == "down"


def test_stable_trend() -> None:
    result = calculate_trend(
        current_pulse=80.0,
        previous_pulse=80.0,
    )

    assert result.change == 0.0
    assert result.direction == "stable"


def test_trend_is_rounded() -> None:
    result = calculate_trend(
        current_pulse=82.37,
        previous_pulse=75.12,
    )

    assert result.change == pytest.approx(7.25)


@pytest.mark.parametrize(
    "current_pulse",
    [-1.0, 100.1],
)
def test_invalid_current_pulse_rejected(current_pulse: float) -> None:
    with pytest.raises(ValueError):
        calculate_trend(
            current_pulse=current_pulse,
            previous_pulse=50.0,
        )


@pytest.mark.parametrize(
    "previous_pulse",
    [-1.0, 100.1],
)
def test_invalid_previous_pulse_rejected(previous_pulse: float) -> None:
    with pytest.raises(ValueError):
        calculate_trend(
            current_pulse=50.0,
            previous_pulse=previous_pulse,
        )
