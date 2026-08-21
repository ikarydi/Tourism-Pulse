"""Network client for the YouTube Data API v3 `search.list` endpoint.

Kept separate from parser.py so unit tests can exercise the parser against
a fixture response without ever touching the network. Requires an API key
(enable the YouTube Data API v3 at https://console.cloud.google.com/) -
never hardcoded, passed in explicitly by the caller (see
settings.youtube_api_key).
"""

import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.youtube.parser import YOUTUBE_SEARCH_BASE_URL

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RESULTS = 25


def build_search_request_url(
    *,
    api_key: str,
    query: str,
    region_code: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    base_url: str = YOUTUBE_SEARCH_BASE_URL,
) -> str:
    params = {
        "key": api_key,
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": str(max_results),
    }

    if region_code is not None:
        params["regionCode"] = region_code

    return f"{base_url}?{urllib.parse.urlencode(params)}"


def build_public_search_source_url(
    *,
    query: str,
    region_code: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    base_url: str = YOUTUBE_SEARCH_BASE_URL,
) -> str:
    """Same query as `build_search_request_url`, but with the API key
    redacted.

    This is what gets stored as a SourceObservation's `source_url` - the
    real fetch URL (with `key`) must never be persisted or displayed,
    since that would leak the secret into the database and, from there,
    the dashboard.
    """
    return build_search_request_url(
        api_key="REDACTED",
        query=query,
        region_code=region_code,
        max_results=max_results,
        base_url=base_url,
    )


def fetch_search_results(
    *,
    api_key: str,
    query: str,
    region_code: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch search results for a query and return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_search_request_url(
        api_key=api_key,
        query=query,
        region_code=region_code,
        max_results=max_results,
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")
