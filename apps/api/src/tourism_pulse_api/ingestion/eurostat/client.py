"""Network client for the Eurostat dissemination API.

Kept separate from parser.py so unit tests can exercise the parsers against
fixtures without ever touching the network. No API key required.
"""

import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.eurostat.parser import (
    ARRIVALS_BASE_URL,
    CAPACITY_BASE_URL,
    CAPACITY_FIXED_PARAMS,
    EUROSTAT_FIXED_PARAMS,
    NIGHTS_BASE_URL,
    OCCUPANCY_BASE_URL,
    OCCUPANCY_FIXED_PARAMS,
)

DEFAULT_TIMEOUT_SECONDS = 20.0


def _build_url(
    *,
    base_url: str,
    geo: str,
    fixed_params: dict[str, str],
    since_time_period: str | None,
) -> str:
    params = {
        "format": "JSON",
        "lang": "EN",
        "geo": geo,
        **fixed_params,
    }

    if since_time_period is not None:
        params["sinceTimePeriod"] = since_time_period

    return f"{base_url}?{urllib.parse.urlencode(params)}"


def build_request_url(
    *,
    geo: str,
    since_time_period: str | None = None,
    base_url: str = NIGHTS_BASE_URL,
) -> str:
    """URL for the nights-spent dataset (tour_occ_nim) - the historical default."""
    return _build_url(
        base_url=base_url,
        geo=geo,
        fixed_params=EUROSTAT_FIXED_PARAMS,
        since_time_period=since_time_period,
    )


def build_arrivals_request_url(*, geo: str, since_time_period: str | None = None) -> str:
    return _build_url(
        base_url=ARRIVALS_BASE_URL,
        geo=geo,
        fixed_params=EUROSTAT_FIXED_PARAMS,
        since_time_period=since_time_period,
    )


def build_occupancy_request_url(*, geo: str, since_time_period: str | None = None) -> str:
    return _build_url(
        base_url=OCCUPANCY_BASE_URL,
        geo=geo,
        fixed_params=OCCUPANCY_FIXED_PARAMS,
        since_time_period=since_time_period,
    )


def build_capacity_request_url(*, geo: str, since_time_period: str | None = None) -> str:
    return _build_url(
        base_url=CAPACITY_BASE_URL,
        geo=geo,
        fixed_params=CAPACITY_FIXED_PARAMS,
        since_time_period=since_time_period,
    )


def _fetch(url: str, *, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")


def fetch_tourism_nights(
    *,
    geo: str,
    since_time_period: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch monthly nights spent for a Eurostat geo code and return raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_request_url(geo=geo, since_time_period=since_time_period)
    return _fetch(url, timeout=timeout)


def fetch_arrivals(
    *,
    geo: str,
    since_time_period: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch monthly tourist arrivals for a Eurostat geo code and return raw JSON text."""
    url = build_arrivals_request_url(geo=geo, since_time_period=since_time_period)
    return _fetch(url, timeout=timeout)


def fetch_occupancy_rate(
    *,
    geo: str,
    since_time_period: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch monthly bed-place occupancy rate for a Eurostat geo code and return raw JSON text."""
    url = build_occupancy_request_url(geo=geo, since_time_period=since_time_period)
    return _fetch(url, timeout=timeout)


def fetch_capacity(
    *,
    geo: str,
    since_time_period: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch annual bed-place capacity for a Eurostat geo code and return raw JSON text."""
    url = build_capacity_request_url(geo=geo, since_time_period=since_time_period)
    return _fetch(url, timeout=timeout)
