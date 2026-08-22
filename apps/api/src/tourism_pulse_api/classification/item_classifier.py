"""Shared keyword/category classifier for item-level content - news
article titles (GDELT) and video titles (YouTube) alike.

Answers "25 articles about Lyon has to be measured, connected to the
rest of the dimensions" (and the same for video search results): a raw
mention/result *count* only ever speaks to `demand` (attention volume),
which is all GDELT's news_mentions and YouTube's search_interest could
ever say on their own. Tagging each individual item lets the ingestion
adapters also count how many of those items are about an event, a
hazard, or the local economy - and write additional signal_types that
feed `events`/`risk`/`economic` too, not just `demand`.

Plain keyword/regex matching, not GDELT's own GKG theme taxonomy
(2,500+ CAMEO/World-Bank categories) or an NLP/ML classifier: GKG is
GDELT-specific and wouldn't apply the same way to YouTube titles, and a
small, readable, source-agnostic keyword list is easier to reason about
and extend than a model this project has no training data for. A
documented starting point - the keyword lists below are illustrative,
not exhaustive; revisit once real title text is observed.

An item can match multiple categories (rare but possible - e.g. "flood
forces festival cancellation"), or none (the common case: general
destination-attention content with no specific topic - still counted
toward the source's demand-side mention total by the caller, just not
toward a more specific dimension).
"""

import re
from enum import StrEnum


class ItemCategory(StrEnum):
    EVENTS = "events"
    RISK = "risk"
    ECONOMIC = "economic"


_KEYWORDS: dict[ItemCategory, list[str]] = {
    ItemCategory.EVENTS: [
        "festival", "concert", "match", "marathon", "exhibition",
        "parade", "tournament", "conference", "carnival", "celebration",
        "premiere", "gala", "expo",
    ],
    # Deliberately no bare "fire" - too many benign compound words start
    # with it at a real word boundary (firewood, firefighter, fireplace,
    # firework); "wildfire" covers the primary tourism-relevant case
    # without that false-positive risk.
    ItemCategory.RISK: [
        "earthquake", "flood", "wildfire", "storm", "hurricane",
        "cyclone", "evacuat", "strike", "protest", "riot", "closure",
        "closed", "warning", "outbreak", "emergency", "attack",
        "unrest", "disaster", "landslide", "eruption",
    ],
    ItemCategory.ECONOMIC: [
        "price", "prices", "inflation", "investment", "tax", "budget",
        "economy", "economic", "spending", "revenue", "turnover", "gdp",
        "recession", "subsidy", "surcharge", "fee", "fees",
    ],
}

# Word-boundary-anchored so "fire" doesn't match "fired up" mid-word in
# an unrelated sense as loosely, and "\b" lets a stem like "evacuat"
# still match "evacuated"/"evacuation" - re.escape() keeps every literal
# keyword safe regardless of what's in the list above.
_PATTERNS: dict[ItemCategory, re.Pattern[str]] = {
    category: re.compile(
        r"\b(" + "|".join(re.escape(keyword) for keyword in keywords) + r")",
        re.IGNORECASE,
    )
    for category, keywords in _KEYWORDS.items()
}


def classify_item(title: str) -> set[ItemCategory]:
    """Return every category whose keywords appear in `title`.

    An empty set means "general attention" - no specific topic matched.
    """
    return {category for category, pattern in _PATTERNS.items() if pattern.search(title)}
