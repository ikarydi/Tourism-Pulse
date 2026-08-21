import pytest

from tourism_pulse_api.pulse.normalization import (
    clamp,
    normalize_inverse,
    normalize_min_max,
    normalize_percentage,
    normalize_sentiment,
)


def test_clamp() -> None:
    assert clamp(0.5) == 0.5
    assert clamp(-0.5) == 0.0
    assert clamp(1.5) == 1.0


def test_normalize_min_max() -> None:
    assert normalize_min_max(0, 0, 100) == 0.0
    assert normalize_min_max(50, 0, 100) == 0.5
    assert normalize_min_max(100, 0, 100) == 1.0


def test_normalize_min_max_clamps() -> None:
    assert normalize_min_max(-10, 0, 100) == 0.0
    assert normalize_min_max(110, 0, 100) == 1.0


def test_normalize_min_max_invalid_range() -> None:
    with pytest.raises(ValueError):
        normalize_min_max(50, 100, 100)


def test_normalize_percentage() -> None:
    assert normalize_percentage(0) == 0.0
    assert normalize_percentage(50) == 0.5
    assert normalize_percentage(100) == 1.0


def test_normalize_percentage_clamps() -> None:
    assert normalize_percentage(-10) == 0.0
    assert normalize_percentage(120) == 1.0


def test_normalize_sentiment() -> None:
    assert normalize_sentiment(-1.0) == 0.0
    assert normalize_sentiment(0.0) == 0.5
    assert normalize_sentiment(1.0) == 1.0


def test_normalize_sentiment_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_sentiment(1.5)


def test_normalize_inverse() -> None:
    assert normalize_inverse(0, 0, 100) == 1.0
    assert normalize_inverse(50, 0, 100) == 0.5
    assert normalize_inverse(100, 0, 100) == 0.0


def test_normalize_inverse_clamps() -> None:
    assert normalize_inverse(-10, 0, 100) == 1.0
    assert normalize_inverse(110, 0, 100) == 0.0


def test_normalize_inverse_invalid_range() -> None:
    with pytest.raises(ValueError):
        normalize_inverse(50, 100, 100)
