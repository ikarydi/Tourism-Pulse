import pytest
from tourism_pulse_api.pulse.signal_normalization import (
    normalize_signal,
)


def test_occupancy_normalization() -> None:
    assert normalize_signal("occupancy", 70) == 0.7


def test_hotel_occupancy_normalization() -> None:
    assert normalize_signal("hotel_occupancy", 85) == 0.85


def test_sentiment_normalization() -> None:
    assert normalize_signal("sentiment", -0.2) == 0.4


def test_weather_comfort_normalization() -> None:
    assert normalize_signal("weather_comfort", 80) == 0.8


def test_occupancy_rate_normalization() -> None:
    # Eurostat's occupancy rate is already a bounded percentage - it goes
    # through the same generic pathway as occupancy/hotel_occupancy, no
    # seasonal baseline required.
    assert normalize_signal("occupancy_rate", 34.3) == pytest.approx(0.343)


def test_signal_type_is_case_insensitive() -> None:
    assert normalize_signal("OCCUPANCY", 70) == 0.7


def test_unknown_signal_type_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_signal("unknown_signal", 50)
