import pytest

from tourism_pulse_api.pulse.effective_signal import (
    calculate_effective_signal,
)


def test_effective_signal_all_maximum() -> None:
    assert calculate_effective_signal(1.0, 1.0, 1.0) == 1.0


def test_effective_signal_is_multiplicative() -> None:
    assert calculate_effective_signal(0.8, 0.5, 0.9) == pytest.approx(0.36)


def test_zero_signal_produces_zero() -> None:
    assert calculate_effective_signal(0.0, 1.0, 1.0) == 0.0


def test_zero_freshness_produces_zero() -> None:
    assert calculate_effective_signal(1.0, 0.0, 1.0) == 0.0


def test_zero_reliability_produces_zero() -> None:
    assert calculate_effective_signal(1.0, 1.0, 0.0) == 0.0


def test_values_above_one_are_clamped() -> None:
    assert calculate_effective_signal(1.5, 2.0, 1.2) == 1.0


def test_negative_values_are_clamped() -> None:
    assert calculate_effective_signal(-1.0, -0.5, -2.0) == 0.0
