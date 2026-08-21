"""Normalizes an OpenSky airborne-aircraft count into a 0-1 Pulse Engine
input.

Reuses `pulse.poi_density`'s saturating-log formula, same as
`pulse.news_mentions`/`pulse.search_interest` - an aircraft count is
unbounded, count-like data.

This is a weaker normalization than the other count-based signals: the
raw count scales with the *bounding box area* the caller queries, which
is not fixed the way OSM's fixed-radius search or a search-engine result
count is. `AIRPORT_TRAFFIC_REFERENCE_COUNT` therefore only means anything
if the same place is always queried with roughly the same bounding box
run to run - see ingestion.opensky's docstring for that convention. A
considered starting point, not a measured constant.
"""

from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# A bounding box around a busy European hub airport tends to show on the
# order of a few dozen airborne aircraft at any moment; used as the
# "busy airspace" anchor.
AIRPORT_TRAFFIC_REFERENCE_COUNT = 50


def normalize_airport_traffic(aircraft_count: float) -> float:
    return normalize_poi_count(aircraft_count, reference_count=AIRPORT_TRAFFIC_REFERENCE_COUNT)
