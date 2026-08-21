"""Deterministic, documented tourism weather-comfort scoring.

No weather provider publishes a single "comfort" percentage - it has to be
derived from raw meteorological readings (temperature, precipitation, wind).
This module is that derivation: a transparent, bounded, configurable formula
from three raw readings to one 0-100 comfort score, kept separate from the
raw readings themselves (which are stored as their own signals - see
`ingestion.weather.service`).

Each factor is scored 0-100 independently via a piecewise-linear preference
curve, then combined as a weighted sum:

    comfort = temperature_comfort * TEMPERATURE_WEIGHT
            + precipitation_comfort * PRECIPITATION_WEIGHT
            + wind_comfort * WIND_WEIGHT

Temperature dominates (0.60) since it is the primary driver of outdoor
tourism comfort; precipitation (0.25) and wind (0.15) are secondary. All
thresholds and weights are named module-level constants, not embedded
magic numbers, so they can be tuned without touching the formula's shape.

Temperature comfort is a trapezoid: 100 within the ideal range, falling
linearly to 0 at the cold/hot limits, 0 beyond them.

Precipitation and wind comfort are both linear ramps from 100 (none) down
to 0 at a defined "uncomfortable" threshold, then floored at 0 beyond it.
"""

from tourism_pulse_api.pulse.normalization import clamp

# Temperature preference curve (degrees Celsius).
IDEAL_TEMP_MIN_C = 18.0
IDEAL_TEMP_MAX_C = 24.0
COLD_LIMIT_C = -5.0  # comfort reaches 0 at or below this
HOT_LIMIT_C = 38.0  # comfort reaches 0 at or above this

# Linear ramps to 0 comfort.
HEAVY_PRECIPITATION_MM = 5.0  # current-conditions precipitation, mm
STRONG_WIND_KMH = 40.0

TEMPERATURE_WEIGHT = 0.60
PRECIPITATION_WEIGHT = 0.25
WIND_WEIGHT = 0.15

_WEIGHT_SUM = TEMPERATURE_WEIGHT + PRECIPITATION_WEIGHT + WIND_WEIGHT
assert abs(_WEIGHT_SUM - 1.0) < 1e-9, f"comfort weights must sum to 1.0, got {_WEIGHT_SUM}"


def temperature_comfort(temperature_c: float) -> float:
    """0-100 comfort from temperature alone: a trapezoid peaking in the ideal range."""
    if IDEAL_TEMP_MIN_C <= temperature_c <= IDEAL_TEMP_MAX_C:
        return 100.0

    if temperature_c < IDEAL_TEMP_MIN_C:
        if temperature_c <= COLD_LIMIT_C:
            return 0.0
        return (
            100.0
            * (temperature_c - COLD_LIMIT_C)
            / (IDEAL_TEMP_MIN_C - COLD_LIMIT_C)
        )

    if temperature_c >= HOT_LIMIT_C:
        return 0.0

    return 100.0 * (HOT_LIMIT_C - temperature_c) / (HOT_LIMIT_C - IDEAL_TEMP_MAX_C)


def precipitation_comfort(precipitation_mm: float) -> float:
    """0-100 comfort from precipitation alone: 100 at none, 0 at/above the threshold."""
    if precipitation_mm < 0:
        raise ValueError("precipitation_mm cannot be negative")

    return max(0.0, 100.0 * (1.0 - precipitation_mm / HEAVY_PRECIPITATION_MM))


def wind_comfort(wind_speed_kmh: float) -> float:
    """0-100 comfort from wind alone: 100 at calm, 0 at/above the threshold."""
    if wind_speed_kmh < 0:
        raise ValueError("wind_speed_kmh cannot be negative")

    return max(0.0, 100.0 * (1.0 - wind_speed_kmh / STRONG_WIND_KMH))


def calculate_weather_comfort(
    *,
    temperature_c: float,
    precipitation_mm: float,
    wind_speed_kmh: float,
) -> float:
    """Weighted-sum tourism weather-comfort score, bounded to [0, 100]."""
    score = (
        temperature_comfort(temperature_c) * TEMPERATURE_WEIGHT
        + precipitation_comfort(precipitation_mm) * PRECIPITATION_WEIGHT
        + wind_comfort(wind_speed_kmh) * WIND_WEIGHT
    )

    return clamp(score, 0.0, 100.0)
