"""Network client for GISCO's NUTS GeoJSON distribution.

Kept separate from parser.py so unit tests can exercise the parser
against a fixture without touching the network.
"""

import urllib.request

from tourism_pulse_api.ingestion.nuts.parser import build_geojson_url

DEFAULT_TIMEOUT_SECONDS = 120.0


def fetch_nuts_geojson(
    *,
    level: int,
    version: str,
    scale: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    request = urllib.request.Request(
        build_geojson_url(level=level, version=version, scale=scale),
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8")
