"""Parser for the YouTube Data API v3 `search.list` response.

https://developers.google.com/youtube/v3/docs/search/list

Uses `pageInfo.totalResults` as a search-interest proxy signal - "how many
videos does YouTube return for this destination-related query right now"
is a search-interest/behavioral signal in the same spirit as spec section
6.3's example `search_interest` signal type, not an authoritative figure
(hence the "social" reliability tier - see the add_sources_table
migration's youtube row).

`videos.list` view/comment-count statistics on the returned items would
give a richer, engagement-weighted signal, but that is a natural next
step, not built this round - see the package docstring.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

YOUTUBE_SOURCE_NAME = "youtube"
YOUTUBE_SEARCH_BASE_URL = "https://www.googleapis.com/youtube/v3/search"

# How many result titles to keep for a human-readable preview - just a
# sample, not the full result set (YouTube caps search.list at 50 items
# per page regardless).
_SAMPLE_TITLE_COUNT = 5


@dataclass(frozen=True)
class YoutubeSearchObservation:
    """One search.list response for one query, straight from YouTube."""

    query: str
    total_results: int
    retrieved_at: datetime
    sample_video_titles: list[str]


def parse_youtube_search(text: str, *, query: str) -> YoutubeSearchObservation:
    """Parse a YouTube `search.list` JSON response into a
    YoutubeSearchObservation.

    Raises `ValueError` if the response is not valid JSON or is missing an
    expected field - a malformed/unexpected response must not silently
    produce a fabricated observation.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"YouTube response is not valid JSON: {exc}") from exc

    try:
        total_results = int(payload["pageInfo"]["totalResults"])
        sample_video_titles = [
            item["snippet"]["title"] for item in payload.get("items", [])[:_SAMPLE_TITLE_COUNT]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected YouTube response shape: {exc}") from exc

    if total_results < 0:
        raise ValueError(f"YouTube reported a negative totalResults: {total_results}")

    return YoutubeSearchObservation(
        query=query,
        total_results=total_results,
        retrieved_at=datetime.now(UTC),
        sample_video_titles=sample_video_titles,
    )
