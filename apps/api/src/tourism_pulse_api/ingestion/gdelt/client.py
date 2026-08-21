"""Network client for the GDELT DOC 2.0 API.

Kept separate from parser.py so unit tests can exercise the parser
against a fixture response without ever touching the network. Unlike
Ticketmaster/YouTube, GDELT requires no API key at all - there is
nothing to redact from a stored source_url.

GDELT asks callers to keep requests to roughly one per 5 seconds
("Please limit requests to one every 5 seconds") - a single ingestion
run only ever makes one request (see __main__.py's --mode flag), so
this is naturally respected as long as a scheduler doesn't run both
modes back-to-back for the same place within that window.
"""

import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.gdelt.parser import GDELT_DOC_BASE_URL

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_TIMESPAN = "1w"
DEFAULT_MAX_RECORDS = 250


def build_artlist_url(
    *,
    query: str,
    timespan: str = DEFAULT_TIMESPAN,
    max_records: int = DEFAULT_MAX_RECORDS,
    base_url: str = GDELT_DOC_BASE_URL,
) -> str:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "timespan": timespan,
        "maxrecords": str(max_records),
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def build_timelinetone_url(
    *,
    query: str,
    timespan: str = DEFAULT_TIMESPAN,
    base_url: str = GDELT_DOC_BASE_URL,
) -> str:
    params = {
        "query": query,
        "mode": "timelinetone",
        "format": "json",
        "timespan": timespan,
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def _fetch(url: str, *, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")


def fetch_artlist(
    *,
    query: str,
    timespan: str = DEFAULT_TIMESPAN,
    max_records: int = DEFAULT_MAX_RECORDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch matching articles for a query and return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_artlist_url(query=query, timespan=timespan, max_records=max_records)
    return _fetch(url, timeout=timeout)


def fetch_timelinetone(
    *,
    query: str,
    timespan: str = DEFAULT_TIMESPAN,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch the tone timeline for a query and return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_timelinetone_url(query=query, timespan=timespan)
    return _fetch(url, timeout=timeout)
