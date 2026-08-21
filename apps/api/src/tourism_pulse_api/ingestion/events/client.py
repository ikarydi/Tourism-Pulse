"""Network client for the Ticketmaster Discovery API.

Kept separate from parser.py so unit tests can exercise the parser against a
fixture response without ever touching the network. Requires an API key
(free signup at https://developer.ticketmaster.com/) - never hardcoded,
passed in explicitly by the caller (see settings.ticketmaster_api_key).
"""

import urllib.parse
import urllib.request
from datetime import datetime

from tourism_pulse_api.ingestion.events.parser import DISCOVERY_API_BASE_URL

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_SIZE = 50


def build_request_url(
    *,
    api_key: str,
    city: str,
    country_code: str,
    start_date_time: datetime | None = None,
    size: int = DEFAULT_SIZE,
    base_url: str = DISCOVERY_API_BASE_URL,
) -> str:
    params = {
        "apikey": api_key,
        "city": city,
        "countryCode": country_code,
        "size": str(size),
        "sort": "date,asc",
    }

    if start_date_time is not None:
        # Ticketmaster requires this exact format: yyyy-MM-ddTHH:mm:ssZ
        params["startDateTime"] = start_date_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    return f"{base_url}?{urllib.parse.urlencode(params)}"


def build_public_source_url(
    *,
    city: str,
    country_code: str,
    start_date_time: datetime | None = None,
    size: int = DEFAULT_SIZE,
    base_url: str = DISCOVERY_API_BASE_URL,
) -> str:
    """Same query as `build_request_url`, but with the API key redacted.

    This is what gets stored as an Event's `source_url` - the real fetch URL
    (with `apikey`) must never be persisted or displayed, since that would
    leak the secret into the database and, from there, the dashboard.
    """
    return build_request_url(
        api_key="REDACTED",
        city=city,
        country_code=country_code,
        start_date_time=start_date_time,
        size=size,
        base_url=base_url,
    )


def fetch_events(
    *,
    api_key: str,
    city: str,
    country_code: str,
    start_date_time: datetime | None = None,
    size: int = DEFAULT_SIZE,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch events for a city and return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_request_url(
        api_key=api_key,
        city=city,
        country_code=country_code,
        start_date_time=start_date_time,
        size=size,
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")
