"""Normalizes a GDELT news-article match count into a 0-1 Pulse Engine input.

Reuses `pulse.poi_density`'s saturating-log formula rather than duplicating
it - a raw article count is the same kind of unbounded, count-like data as
an OSM hotel/restaurant count or a YouTube search-result count.

One real limitation worth being explicit about: GDELT's ArtList mode caps
results at `maxrecords` (250 max) - so this is not a true total match
count, it saturates at whatever cap the adapter requests. That happens to
compose reasonably with a saturating-log normalizer (heavy coverage
naturally reads as "near 1.0" either way), but it means this signal reads
as "at least this many articles", not "exactly this many".
"""

from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# A destination getting sustained international travel-press attention
# tends to hit GDELT's per-query article cap comfortably within a
# one-week window; used as the "well-covered" anchor, the same role
# HOTEL_REFERENCE_COUNT plays for OSM hotel counts. A considered starting
# point, not a measured constant - revisit once real queries are observed.
NEWS_MENTIONS_REFERENCE_COUNT = 150


def normalize_news_mentions(article_count: float) -> float:
    return normalize_poi_count(article_count, reference_count=NEWS_MENTIONS_REFERENCE_COUNT)
