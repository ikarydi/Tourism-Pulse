"""Parser for the Open-Meteo current-weather API response.

https://open-meteo.com/en/docs

Unlike the KSH sources, this is a live/near-real-time source: one request
returns the current conditions at a point in time, not a historical monthly
series. There is no seasonal baseline concept here - a single reading is
directly meaningful ("22 degrees, no rain, light wind right now").

The raw JSON response is validated and reshaped into a `WeatherObservation`
here; deriving a comfort score from it lives in `pulse.weather_comfort`
(kept separate - see that module's docstring for why), and turning the
observation into Signal rows lives in `service.py`.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

OPEN_METEO_SOURCE_NAME = "open-meteo"
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes (https://open-meteo.com/en/docs -
# "WMO Weather interpretation codes (WW)"), used only for a human-readable
# label - never for the comfort score itself, which is derived purely from
# the numeric readings.
WMO_WEATHER_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass(frozen=True)
class WeatherObservation:
    """Current conditions at one point in time, straight from Open-Meteo."""

    observed_at: datetime
    latitude: float
    longitude: float
    temperature_c: Decimal
    humidity_percent: Decimal
    precipitation_mm: Decimal
    wind_speed_kmh: Decimal
    weather_code: int

    @property
    def weather_description(self) -> str:
        return WMO_WEATHER_DESCRIPTIONS.get(self.weather_code, "Unknown conditions")


def build_request_url(
    *,
    latitude: float,
    longitude: float,
    base_url: str = OPEN_METEO_BASE_URL,
) -> str:
    return (
        f"{base_url}?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,relative_humidity_2m,precipitation,"
        "wind_speed_10m,weather_code&timezone=UTC"
    )


def parse_open_meteo_current(text: str) -> WeatherObservation:
    """Parse an Open-Meteo `current=...` JSON response into a WeatherObservation.

    Raises `ValueError` if the response is not valid JSON or is missing an
    expected field - a malformed/unexpected response must not silently
    produce a fabricated observation.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Open-Meteo response is not valid JSON: {exc}") from exc

    try:
        current = payload["current"]
        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
        observed_at = datetime.fromisoformat(current["time"]).replace(tzinfo=UTC)
        temperature_c = Decimal(str(current["temperature_2m"]))
        humidity_percent = Decimal(str(current["relative_humidity_2m"]))
        precipitation_mm = Decimal(str(current["precipitation"]))
        wind_speed_kmh = Decimal(str(current["wind_speed_10m"]))
        weather_code = int(current["weather_code"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected Open-Meteo response shape: {exc}") from exc

    return WeatherObservation(
        observed_at=observed_at,
        latitude=latitude,
        longitude=longitude,
        temperature_c=temperature_c,
        humidity_percent=humidity_percent,
        precipitation_mm=precipitation_mm,
        wind_speed_kmh=wind_speed_kmh,
        weather_code=weather_code,
    )
