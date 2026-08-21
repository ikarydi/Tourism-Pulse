import pytest

from tourism_pulse_api.pulse.calculator import PulseCalculator


def test_calculator_returns_weighted_pulse() -> None:
    calculator = PulseCalculator()

    result = calculator.calculate(
        demand=0.78,
        capacity=0.71,
        events=0.91,
        environment=0.84,
    )

    assert result.pulse == pytest.approx(80.05)
    assert result.demand == 78.0
    assert result.capacity == 71.0
    assert result.events == 91.0
    assert result.environment == 84.0


def test_all_zero_produces_zero() -> None:
    calculator = PulseCalculator()

    result = calculator.calculate(
        demand=0.0,
        capacity=0.0,
        events=0.0,
        environment=0.0,
    )

    assert result.pulse == 0.0


def test_all_one_produces_100() -> None:
    calculator = PulseCalculator()

    result = calculator.calculate(
        demand=1.0,
        capacity=1.0,
        events=1.0,
        environment=1.0,
    )

    assert result.pulse == 100.0


@pytest.mark.parametrize(
    "dimension",
    ["demand", "capacity", "events", "environment"],
)
def test_dimension_above_one_rejected(dimension: str) -> None:
    calculator = PulseCalculator()

    values = {
        "demand": 0.5,
        "capacity": 0.5,
        "events": 0.5,
        "environment": 0.5,
    }

    values[dimension] = 1.1

    with pytest.raises(ValueError):
        calculator.calculate(**values)


@pytest.mark.parametrize(
    "dimension",
    ["demand", "capacity", "events", "environment"],
)
def test_dimension_below_zero_rejected(dimension: str) -> None:
    calculator = PulseCalculator()

    values = {
        "demand": 0.5,
        "capacity": 0.5,
        "events": 0.5,
        "environment": 0.5,
    }

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
        (0.8 * 0.35) + (0.6 * 0.20)
    ) / (0.35 + 0.20)

    assert result.pulse == pytest.approx(
        expected * 100,
        abs=0.01,
    )
    assert result.demand == 80.0
    assert result.capacity == 0.0
    assert result.events == 0.0
    assert result.environment == 60.0