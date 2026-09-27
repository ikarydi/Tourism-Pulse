"""Normalizes a place's tourist-nights-per-resident ratio ("visitor
pressure") into a 0-1 input for the tourism-pressure index, which the
engine reports next to the Pulse rather than inside it (see
pulse.engine.PRESSURE_DIMENSION). Higher means more strain.

Reuses `pulse.poi_density`'s saturating-log formula: an unbounded ratio
where sustained tourism activity relative to the resident population
scores near the top, with early growth mattering more than late growth
- the same shape used for POI/search-interest counts.

Deliberately NOT an inverted "overtourism penalty" curve (unlike
pulse.disaster_risk/pulse.air_quality's inverted normalizers):
distinguishing "healthy tourism economy relative to the resident base"
from "over social/physical carrying capacity" needs real destination-
level thresholds this project doesn't have data for yet - a documented
simplification (see ingestion.eurostat's visitor_pressure derivation),
not a finished carrying-capacity model. Revisit once real destinations'
ratios are observed.
"""

from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# Monthly tourist-nights-per-resident ratio treated as "high tourism
# pressure" - a considered starting point (a month where nights spent
# roughly matches the resident population), not a measured
# carrying-capacity threshold.
VISITOR_PRESSURE_REFERENCE_RATIO = 1


def normalize_visitor_pressure(ratio: float) -> float:
    return normalize_poi_count(ratio, reference_count=VISITOR_PRESSURE_REFERENCE_RATIO)
