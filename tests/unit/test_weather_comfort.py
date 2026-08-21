import pytest
from tourism_pulse_api.pulse.weather_comfort import (
    COLD_LIMIT_C,
    HOT_LIMIT_C,
    IDEAL_TEMP_MAX_C,
    IDEAL_TEMP_MIN_C,
    calculate_weather_comfort,
    precipitation_comfort,
    temperature_comfort,
    wind_comfort,
)


def test_temperature_comfort_is_perfect_within_the_ideal_range() -> None:
    assert temperature_comfort(IDEAL_TEMP_MIN_C) == 100.0
    assert temperature_comfort(IDEAL_TEMP_MAX_C) == 100.0
    assert temperature_comfort((IDEAL_TEMP_MIN_C + IDEAL_TEMP_MAX_C) / 2) == 100.0


def test_temperature_comfort_reaches_zero_at_the_limits() -> None:
    assert temperature_comfort(COLD_LIMIT_C) == 0.0
    assert temperature_comfort(HOT_LIMIT_C) == 0.0


def test_temperature_comfort_stays_zero_beyond_the_limits() -> None:
    assert temperature_comfort(COLD_LIMIT_C - 10) == 0.0
    assert temperature_comfort(HOT_LIMIT_C + 10) == 0.0


def test_temperature_comfort_degrades_monotonically_outward() -> None:
    cold_side = [temperature_comfort(t) for t in [COLD_LIMIT_C, 0, 10, IDEAL_TEMP_MIN_C]]
    assert cold_side == sorted(cold_side)

    hot_side = [temperature_comfort(t) for t in [IDEAL_TEMP_MAX_C, 30, 35, HOT_LIMIT_C]]
    assert hot_side == sorted(hot_side, reverse=True)


def test_precipitation_comfort_is_perfect_when_dry() -> None:
    assert precipitation_comfort(0.0) == 100.0


def test_precipitation_comfort_decreases_with_more_rain() -> None:
    assert precipitation_comfort(1.0) > precipitation_comfort(3.0) > precipitation_comfort(5.0)


def test_precipitation_comfort_floors_at_zero() -> None:
    assert precipitation_comfort(100.0) == 0.0


def test_precipitation_comfort_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        precipitation_comfort(-1.0)


def test_wind_comfort_is_perfect_when_calm() -> None:
    assert wind_comfort(0.0) == 100.0


def test_wind_comfort_decreases_with_more_wind() -> None:
    assert wind_comfort(5.0) > wind_comfort(20.0) > wind_comfort(40.0)


def test_wind_comfort_floors_at_zero() -> None:
    assert wind_comfort(100.0) == 0.0


def test_wind_comfort_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        wind_comfort(-1.0)


def test_calculate_weather_comfort_is_perfect_in_ideal_conditions() -> None:
    comfort = calculate_weather_comfort(
        temperature_c=21.0,
        precipitation_mm=0.0,
        wind_speed_kmh=0.0,
    )

    assert comfort == 100.0


def test_calculate_weather_comfort_is_poor_in_harsh_conditions() -> None:
    comfort = calculate_weather_comfort(
        temperature_c=45.0,
        precipitation_mm=20.0,
        wind_speed_kmh=80.0,
    )

    assert comfort == 0.0


@pytest.mark.parametrize(
    ("temperature_c", "precipitation_mm", "wind_speed_kmh"),
    [
        (-30.0, 0.0, 0.0),
        (50.0, 0.0, 0.0),
        (21.0, 100.0, 0.0),
        (21.0, 0.0, 200.0),
        (30.5, 0.0, 10.1),
    ],
)
def test_calculate_weather_comfort_always_within_bounds(
    temperature_c: float,
    precipitation_mm: float,
    wind_speed_kmh: float,
) -> None:
    comfort = calculate_weather_comfort(
        temperature_c=temperature_c,
        precipitation_mm=precipitation_mm,
        wind_speed_kmh=wind_speed_kmh,
    )

    assert 0.0 <= comfort <= 100.0


def test_calculate_weather_comfort_is_deterministic() -> None:
    kwargs = {"temperature_c": 22.5, "precipitation_mm": 0.4, "wind_speed_kmh": 12.0}

    assert calculate_weather_comfort(**kwargs) == calculate_weather_comfort(**kwargs)


def test_calculate_weather_comfort_matches_the_documented_real_world_example() -> None:
    # Budapest, 2026-08-21T10:00 UTC: 30.5C, 0mm rain, 10.1 km/h wind.
    comfort = calculate_weather_comfort(
        temperature_c=30.5,
        precipitation_mm=0.0,
        wind_speed_kmh=10.1,
    )

    assert comfort == pytest.approx(68.36, abs=0.01)
