"""Parser for the GDELT DOC 2.0 API's ArtList and TimelineTone modes.

https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

ArtList's exact JSON shape (verified against a live response):

    {"articles": [{"url", "url_mobile", "title", "seendate",
                   "socialimage", "domain", "language", "sourcecountry"}]}

ArtList does not include a tone/sentiment field - sentiment is only
available via TimelineTone, whose shape (verified against GDELT's own
timeline visualizer source) is:

    {"timeline": [{"data": [{"date": "YYYYMMDDHHMMSS", "value": <tone>}]}]}

The most recent (last) data point is used as "current" tone - the series
covers the whole query window, not one moment in time, but a single most-
recent reading is what a Signal row can meaningfully represent.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

GDELT_SOURCE_NAME = "gdelt"
GDELT_DOC_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# How many article titles to keep for a human-readable preview.
_SAMPLE_TITLE_COUNT = 5


@dataclass(frozen=True)
class GdeltArticleListObservation:
    """One ArtList response for one query, straight from GDELT."""

    query: str
    article_count: int
    retrieved_at: datetime
    sample_article_titles: list[str]


@dataclass(frozen=True)
class GdeltToneObservation:
    """One TimelineTone response for one query - the most recent tone
    reading in the series, straight from GDELT."""

    query: str
    tone: float
    observed_at: datetime


def parse_gdelt_artlist(text: str, *, query: str) -> GdeltArticleListObservation:
    """Raises `ValueError` if the response is not valid JSON or is missing
    an expected field - a malformed/unexpected response (including
    GDELT's plaintext rate-limit notice, which is not valid JSON) must
    not silently produce a fabricated observation.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GDELT response is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"Unexpected GDELT response shape: expected an object, got {type(payload)}"
        )

    # A missing "articles" key is a legitimate zero-result query, not an
    # error - GDELT omits the key entirely rather than returning [].
    articles = payload.get("articles", [])

    try:
        sample_titles = [article["title"] for article in articles[:_SAMPLE_TITLE_COUNT]]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Unexpected GDELT article shape: {exc}") from exc

    return GdeltArticleListObservation(
        query=query,
        article_count=len(articles),
        retrieved_at=datetime.now(UTC),
        sample_article_titles=sample_titles,
    )


def parse_gdelt_timelinetone(text: str, *, query: str) -> GdeltToneObservation:
    """Raises `ValueError` if the response is not valid JSON or is missing
    an expected field, or if the timeline has no data points.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GDELT response is not valid JSON: {exc}") from exc

    try:
        data_points = payload["timeline"][0]["data"]
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError(f"Unexpected GDELT timelinetone response shape: {exc}") from exc

    if not data_points:
        raise ValueError("GDELT timelinetone response has no data points")

    latest = data_points[-1]

    try:
        tone = float(latest["value"])
        observed_at = datetime.strptime(latest["date"], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected GDELT timelinetone data point shape: {exc}") from exc

    return GdeltToneObservation(query=query, tone=tone, observed_at=observed_at)
