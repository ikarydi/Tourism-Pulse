import pytest
from tourism_pulse_api.pulse.calculator import PulseCalculator


def test_calculator_returns_weighted_pulse() -> None:
    calculator = PulseCalculator()

    result = calculator.calculate(
        demand=0.78,
        capacity=0.71,
        events=0.91,
        environment=0.84,
        risk=0.60,
        economic=0.50,
    )

    expected = (
        0.78 * 0.25
        + 0.71 * 0.20
        + 0.91 * 0.15
        + 0.84 * 0.15
        + 0.60 * 0.15
        + 0.50 * 0.10
    ) * 100

    assert result.pulse == pytest.approx(expected, abs=0.01)
    assert result.demand == 78.0
    assert result.capacity == 71.0
    assert result.events == 91.0
    assert result.environment == 84.0
    assert result.risk == 60.0
    assert result.economic == 50.0


def test_all_zero_produces_zero() -> None:
    calculator = PulseCalculator()

    result = calculator.calculate(
        demand=0.0,
        capacity=0.0,
        events=0.0,
        environment=0.0,
        risk=0.0,
        economic=0.0,
    )

    assert result.pulse == 0.0


def test_all_one_produces_100() -> None:
    calculator = PulseCalculator()

    result = calculator.calculate(
        demand=1.0,
        capacity=1.0,
        events=1.0,
        environment=1.0,
        risk=1.0,
        economic=1.0,
    )

    assert result.pulse == 100.0


DIMENSIONS = ["demand", "capacity", "events", "environment", "risk", "economic"]


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_dimension_above_one_rejected(dimension: str) -> None:
    calculator = PulseCalculator()

    values = {name: 0.5 for name in DIMENSIONS}
    values[dimension] = 1.1

    with pytest.raises(ValueError):
        calculator.calculate(**values)


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_dimension_below_zero_rejected(dimension: str) -> None:
    calculator = PulseCalculator()

    values = {name: 0.5 for name in DIMENSIONS}
    values[dimension] = -0.1

    with pytest.raises(ValueError):
        calculator.calculate(**values)


def test_calculator_renormalizes_available_dimensions() -> None:
    calculator = PulseCalculator()

    result = calculator.calculate_available(
        dimensions={
            "demand": 0.8,
            "environment": 0.6,
        },
    )

    expected = (
        (0.8 * 0.25) + (0.6 * 0.15)
    ) / (0.25 + 0.15)

    assert result.pulse == pytest.approx(
        expected * 100,
        abs=0.01,
    )
    assert result.demand == 80.0
    assert result.capacity == 0.0
    assert result.events == 0.0
    assert result.environment == 60.0
    assert result.risk == 0.0
    assert result.economic == 0.0
