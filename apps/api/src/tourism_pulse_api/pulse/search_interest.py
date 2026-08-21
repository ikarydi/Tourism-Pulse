"""Normalizes a YouTube search-result count into a 0-1 Pulse Engine input.

Reuses `pulse.poi_density`'s saturating-log formula rather than
duplicating it: a raw video-result count is the same kind of unbounded,
count-like data as an OSM hotel/restaurant count - "12,000 results" isn't
meaningful without a reference point, and early growth should matter more
than late growth the same way it does for POI density.
"""

from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# A destination with strong, sustained travel-content interest tends to
# return results in the low tens of thousands for a generic
# "<destination> travel guide"-style query; used as the "high interest"
# anchor, the same role HOTEL_REFERENCE_COUNT plays for OSM hotel counts.
# A considered starting point, not a measured constant - revisit once real
# destinations' result counts are observed.
SEARCH_INTEREST_REFERENCE_COUNT = 20_000


def normalize_search_interest(total_results: float) -> float:
    return normalize_poi_count(total_results, reference_count=SEARCH_INTEREST_REFERENCE_COUNT)
