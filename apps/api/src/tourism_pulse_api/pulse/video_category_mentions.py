"""Normalizes a per-category YouTube search-result count
(video_event_mentions / video_risk_mentions / video_economic_mentions -
see classification.item_classifier and ingestion.youtube.service) into
a 0-1 Pulse Engine input.

Reuses `pulse.poi_density`'s saturating-log formula, same idea as
`pulse.news_category_mentions`, but with an even smaller reference
constant: a category count here is a subset of one page of YouTube
search results (--max-results, default 25 - see ingestion.youtube's
DEFAULT_MAX_RESULTS), not GDELT's up-to-250-article page.
"""

from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# A handful of a search page's videos being about the same topic (event/
# hazard/economic) already reads as meaningful coverage, given the small
# total page size. A considered starting point, not a measured constant.
VIDEO_CATEGORY_MENTIONS_REFERENCE_COUNT = 8


def normalize_video_category_mentions(count: float) -> float:
    return normalize_poi_count(count, reference_count=VIDEO_CATEGORY_MENTIONS_REFERENCE_COUNT)
