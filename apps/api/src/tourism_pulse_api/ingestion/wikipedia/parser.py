"""Parser for the Wikimedia Analytics API's per-article pageviews
response.

https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html

Each `items` entry is one day's view count for the requested article.
An empty `items` list is a valid result (a brand-new or extremely
low-traffic article can have zero recorded days in range) - not an
error, the same way OpenSky's null `states` (empty airspace) isn't one.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

WIKIPEDIA_SOURCE_NAME = "wikipedia"
WIKIPEDIA_PAGEVIEWS_BASE_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
)


@dataclass(frozen=True)
class WikipediaPageviewsObservation:
    """One per-article pageviews response for one article/date range."""

    article: str
    project: str
    total_views: int
    daily_views: list[int]
    retrieved_at: datetime


def parse_wikipedia_pageviews(
    text: str,
    *,
    article: str,
    project: str,
) -> WikipediaPageviewsObservation:
    """Parse a Wikimedia per-article pageviews JSON response.

    Raises `ValueError` if the response is not valid JSON or is missing
    an expected field - a malformed/unexpected response must not
    silently produce a fabricated observation.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Wikipedia pageviews response is not valid JSON: {exc}") from exc

    try:
        daily_views = [int(item["views"]) for item in payload.get("items", [])]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected Wikipedia pageviews response shape: {exc}") from exc

    if any(views < 0 for views in daily_views):
        raise ValueError(f"Wikipedia reported a negative daily view count: {daily_views}")

    return WikipediaPageviewsObservation(
        article=article,
        project=project,
        total_views=sum(daily_views),
        daily_views=daily_views,
        retrieved_at=datetime.now(UTC),
    )
