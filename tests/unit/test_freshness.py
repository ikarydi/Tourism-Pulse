import pytest

from tourism_pulse_api.pulse.freshness import calculate_freshness


def test_freshness_at_zero_age() -> None:
    assert calculate_freshness(0, 6) == 1.0


def test_freshness_at_half_life() -> None:
    assert calculate_freshness(6, 6) == 0.5


def test_freshness_at_two_half_lives() -> None:
    assert calculate_freshness(12, 6) == 0.25


def test_freshness_at_three_half_lives() -> None:
    assert calculate_freshness(18, 6) == 0.125


def test_freshness_fractional_age() -> None:
    assert calculate_freshness(3, 6) == pytest.approx(0.70710678)


def test_negative_age_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_freshness(-1, 6)


def test_zero_half_life_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_freshness(6, 0)


def test_negative_half_life_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_freshness(6, -1)
