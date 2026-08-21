"""Open-Meteo current-weather ingestion.

https://open-meteo.com/en/docs - free, no API key required.

Fetches current conditions for a coordinate and derives a `weather_comfort`
signal (see `pulse.weather_comfort`) alongside the raw readings it was
computed from.
"""

from tourism_pulse_api.ingestion.weather.parser import (
    OPEN_METEO_SOURCE_NAME,
    WeatherObservation,
    parse_open_meteo_current,
)

__all__ = [
    "OPEN_METEO_SOURCE_NAME",
    "WeatherObservation",
    "parse_open_meteo_current",
]
