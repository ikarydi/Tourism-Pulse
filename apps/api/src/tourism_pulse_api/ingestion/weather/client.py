"""Network client for the Open-Meteo current-weather API.

Kept separate from parser.py so unit tests can exercise the parser against a
fixture response without ever touching the network. No API key is required.
"""

import urllib.request

from tourism_pulse_api.ingestion.weather.parser import build_request_url

DEFAULT_TIMEOUT_SECONDS = 15.0


def fetch_current_weather(
    *,
    latitude: float,
    longitude: float,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch current weather for a coordinate and return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_request_url(latitude=latitude, longitude=longitude)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")
