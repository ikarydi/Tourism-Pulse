"""Network client for the Wikimedia Analytics API's per-article
pageviews endpoint.

Kept separate from parser.py so unit tests can exercise the parser
against a fixture response without ever touching the network. Fully
keyless - see the package docstring.
"""

import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta

from tourism_pulse_api.ingestion.wikipedia.parser import WIKIPEDIA_PAGEVIEWS_BASE_URL

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_PROJECT = "en.wikipedia.org"
DEFAULT_DAYS = 30
# "user" excludes known bots/spiders from the count - a genuine human-
# attention signal, not inflated by crawler traffic. "all-agents" is the
# other documented option.
DEFAULT_AGENT = "user"
# The pageviews pipeline has a short processing lag; the last couple of
# days are often incomplete or not yet published. Ending the window here
# avoids an artificially low most-recent-day count.
_PROCESSING_LAG_DAYS = 2


def _format_article(article: str) -> str:
    return urllib.parse.quote(article.strip().replace(" ", "_"), safe="")


def build_request_url(
    *,
    article: str,
    project: str = DEFAULT_PROJECT,
    agent: str = DEFAULT_AGENT,
    days: int = DEFAULT_DAYS,
    end_date: date | None = None,
    base_url: str = WIKIPEDIA_PAGEVIEWS_BASE_URL,
) -> str:
    end = end_date or (datetime.now(UTC).date() - timedelta(days=_PROCESSING_LAG_DAYS))
    start = end - timedelta(days=days - 1)

    return (
        f"{base_url}/{project}/all-access/{agent}/"
        f"{_format_article(article)}/daily/"
        f"{start:%Y%m%d}/{end:%Y%m%d}"
    )


def fetch_pageviews(
    *,
    article: str,
    project: str = DEFAULT_PROJECT,
    agent: str = DEFAULT_AGENT,
    days: int = DEFAULT_DAYS,
    end_date: date | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch daily pageviews for an article and return the raw JSON text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    url = build_request_url(
        article=article,
        project=project,
        agent=agent,
        days=days,
        end_date=end_date,
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")
