"""Normalizes a Wikipedia 30-day pageview total into a 0-1 Pulse Engine
input.

Reuses `pulse.poi_density`'s saturating-log formula rather than
duplicating it - the same shape used by search_interest/poi_density: an
unbounded, count-like number where early growth should matter more than
late growth. Kept as its own reference constant (not shared with
`pulse.search_interest`) since a 30-day Wikipedia pageview total and a
YouTube search.list totalResults figure are different orders of
magnitude - see ingestion.wikipedia's package docstring.
"""

from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# A well-known destination's Wikipedia article tends to draw somewhere in
# the low hundreds of thousands of views over 30 days; used as the "high
# interest" anchor, the same role SEARCH_INTEREST_REFERENCE_COUNT plays
# for YouTube. A considered starting point, not a measured constant -
# revisit once real destinations' pageview totals are observed.
WIKIPEDIA_PAGEVIEW_REFERENCE_COUNT = 300_000


def normalize_wikipedia_pageviews(total_views: float) -> float:
    return normalize_poi_count(
        total_views,
        reference_count=WIKIPEDIA_PAGEVIEW_REFERENCE_COUNT,
    )
