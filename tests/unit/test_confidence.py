import pytest

from tourism_pulse_api.pulse.confidence import calculate_confidence


def test_perfect_confidence() -> None:
    result = calculate_confidence(
        average_reliability=1.0,
        average_freshness=1.0,
        dimension_coverage=1.0,
    )

    assert result.score == 100.0
    assert result.reliability == 100.0
    assert result.freshness == 100.0
    assert result.coverage == 100.0


def test_weighted_confidence() -> None:
    result = calculate_confidence(
        average_reliability=0.8,
        average_freshness=0.6,
        dimension_coverage=0.9,
    )

    expected = (
        0.8 * 0.40
        + 0.6 * 0.30
        + 0.9 * 0.30
    ) * 100

    assert result.score == pytest.approx(expected)


def test_zero_confidence() -> None:
    result = calculate_confidence(
        average_reliability=0.0,
        average_freshness=0.0,
        dimension_coverage=0.0,
    )

    assert result.score == 0.0


@pytest.mark.parametrize(
    "field",
    [
        "average_reliability",
        "average_freshness",
        "dimension_coverage",
    ],
)
def test_values_above_one_rejected(field: str) -> None:
    values = {
        "average_reliability": 0.5,
        "average_freshness": 0.5,
        "dimension_coverage": 0.5,
    }

    values[field] = 1.1

    with pytest.raises(ValueError):
        calculate_confidence(**values)


@pytest.mark.parametrize(
    "field",
    [
        "average_reliability",
        "average_freshness",
        "dimension_coverage",
    ],
)
def test_negative_values_rejected(field: str) -> None:
    values = {
        "average_reliability": 0.5,
        "average_freshness": 0.5,
        "dimension_coverage": 0.5,
    }

    values[field] = -0.1

    with pytest.raises(ValueError):
        calculate_confidence(**values)
