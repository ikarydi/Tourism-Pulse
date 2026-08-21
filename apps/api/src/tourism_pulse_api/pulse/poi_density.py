"""Normalizes a raw OpenStreetMap POI count into a 0-1 Pulse Engine input.

A hotel or restaurant *count* has no natural 0-100 scale the way a
percentage does - "83 hotels" isn't meaningful without a reference point.
This uses a saturating log curve rather than a hard linear cap:

    score = min(1.0, log(1 + count) / log(1 + REFERENCE_COUNT))

`REFERENCE_COUNT` is the count treated as "as well-provisioned as a
major, mature tourist hub" (score 1.0 and above). The log keeps early
growth steep - going from 0 to 20 hotels is a much bigger jump in tourism
infrastructure than going from 200 to 220 - matching how each additional
venue matters less once a destination is already saturated with them.
These reference values are a considered starting point, not a measured
constant; revisit if real destinations cluster oddly against them.
"""

import math

# A well-established European tourist city (e.g. mid-sized capital) tends
# to have on the order of a couple hundred hotels within a city-scale
# radius; used as the "fully provisioned" anchor for the hotel signal.
HOTEL_REFERENCE_COUNT = 200

# Restaurants are far more numerous than hotels in any city regardless of
# tourism intensity, so the reference count is set proportionally higher.
RESTAURANT_REFERENCE_COUNT = 500


def normalize_poi_count(count: float, *, reference_count: int) -> float:
    if count <= 0:
        return 0.0

    return min(1.0, math.log1p(count) / math.log1p(reference_count))


def normalize_hotel_count(count: float) -> float:
    return normalize_poi_count(count, reference_count=HOTEL_REFERENCE_COUNT)


def normalize_restaurant_count(count: float) -> float:
    return normalize_poi_count(count, reference_count=RESTAURANT_REFERENCE_COUNT)
