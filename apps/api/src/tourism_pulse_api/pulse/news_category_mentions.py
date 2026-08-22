"""Normalizes a per-category GDELT article count (news_event_mentions /
news_risk_mentions / news_economic_mentions - see
classification.item_classifier and ingestion.gdelt.service) into a 0-1
Pulse Engine input.

Reuses `pulse.poi_density`'s saturating-log formula, same as
`pulse.news_mentions`, but with its own (smaller) reference constant: a
category count is always a subset of the total article count
(news_mentions), so it needs a lower "well-covered" anchor to still
read as meaningful at realistic subset sizes.
"""

from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# A destination getting sustained topic-specific coverage (e.g. a real
# ongoing event, or a real ongoing hazard) might see a few dozen
# category-tagged articles within a one-week window - well below
# news_mentions' 150-article "well-covered" anchor, since this is
# always a subset of that total. A considered starting point, not a
# measured constant - revisit once real category counts are observed.
NEWS_CATEGORY_MENTIONS_REFERENCE_COUNT = 30


def normalize_news_category_mentions(count: float) -> float:
    return normalize_poi_count(count, reference_count=NEWS_CATEGORY_MENTIONS_REFERENCE_COUNT)
