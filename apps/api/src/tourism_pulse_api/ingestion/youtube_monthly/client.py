"""YouTube Data API v3 `search.list` filtered to one upload month.

Each call costs 100 quota units; the default project quota is 10,000 a
day, so about 100 months a day. The key is passed in by the caller and
never stored: `public_source_url` redacts it.
"""

import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.social_monthly import month_start, next_month

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
QUOTA_UNITS_PER_CALL = 100


def _rfc3339(month: str) -> str:
    return month_start(month).strftime("%Y-%m-%dT%H:%M:%SZ")


def monthly_request_url(*, api_key: str, query: str, month: str) -> str:
    params = {
        "key": api_key,
        "q": query,
        "part": "id",
        "type": "video",
        "maxResults": "1",
        "publishedAfter": _rfc3339(month),
        "publishedBefore": _rfc3339(next_month(month)),
    }
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def public_source_url(*, query: str, month: str) -> str:
    return monthly_request_url(api_key="REDACTED", query=query, month=month)


def fetch_month(*, api_key: str, query: str, month: str, timeout: float = 30.0) -> str:
    request = urllib.request.Request(
        monthly_request_url(api_key=api_key, query=query, month=month),
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8")
