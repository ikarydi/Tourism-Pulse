"""Network client for GDACS's `geteventlist/SEARCH` endpoint.

Kept separate from parser.py so unit tests can exercise the parser
against a fixture response without ever touching the network. Fully
keyless - see the package docstring.
"""

import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.gdacs.parser import GDACS_EVENTS_BASE_URL

DEFAULT_TIMEOUT_SECONDS = 15.0


def build_request_url(
    *,
    country: str,
    base_url: str = GDACS_EVENTS_BASE_URL,
) -> str:
    params = {"country": country}
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def fetch_events(
    *,
    country: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch current/recent disaster-alert events for a country and
    return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_request_url(country=country)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")
