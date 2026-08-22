"""Network client for OpenAQ v3's `/locations` and `/locations/{id}/latest`
endpoints.

Kept separate from parser.py so unit tests can exercise the parser
against fixture responses without ever touching the network. Requires
an API key (register at https://explore.openaq.org/register) - never
hardcoded, passed in explicitly by the caller (see
settings.openaq_api_key).
"""

import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.openaq.parser import OPENAQ_API_BASE_URL

DEFAULT_TIMEOUT_SECONDS = 15.0
# OpenAQ's geospatial radius query caps at 25km.
DEFAULT_RADIUS_METERS = 25_000


def build_locations_url(
    *,
    latitude: float,
    longitude: float,
    radius_meters: int = DEFAULT_RADIUS_METERS,
    base_url: str = OPENAQ_API_BASE_URL,
) -> str:
    params = {
        "coordinates": f"{latitude},{longitude}",
        "radius": str(radius_meters),
    }
    return f"{base_url}/locations?{urllib.parse.urlencode(params)}"


def build_latest_url(
    *,
    location_id: int,
    base_url: str = OPENAQ_API_BASE_URL,
) -> str:
    return f"{base_url}/locations/{location_id}/latest"


def _get(url: str, *, api_key: str, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "tourism-pulse-ingestion/1.0",
            "X-API-Key": api_key,
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")


def fetch_nearest_locations(
    *,
    api_key: str,
    latitude: float,
    longitude: float,
    radius_meters: int = DEFAULT_RADIUS_METERS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch monitoring stations within `radius_meters` of a point and
    return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_locations_url(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )
    return _get(url, api_key=api_key, timeout=timeout)


def fetch_latest_measurements(
    *,
    api_key: str,
    location_id: int,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch one station's latest per-sensor readings and return the raw
    JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_latest_url(location_id=location_id)
    return _get(url, api_key=api_key, timeout=timeout)
