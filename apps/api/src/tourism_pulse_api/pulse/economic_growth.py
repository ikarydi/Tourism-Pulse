"""Normalizes a year-over-year accommodation-sector turnover growth
rate (percent) into a 0-1 Pulse Engine input for the `economic`
dimension.

Unlike occupancy_rate's direct percentage mapping (already 0-100
bounded), a growth rate can be negative (a shrinking sector) or exceed
100 in rare cases, so this clamps to a considered symmetric range
around 0% and maps linearly - 0% growth (a flat, neither-growing-nor-
shrinking sector) is the midpoint, not the floor.
"""

# A considered symmetric anchor, not a measured constant: +/-20% annual
# turnover growth for a whole national accommodation sector would
# already be a dramatic swing in either direction.
GROWTH_RATE_CLAMP_PERCENT = 20.0


def normalize_turnover_growth(percent_change: float) -> float:
    clamped = max(
        -GROWTH_RATE_CLAMP_PERCENT,
        min(percent_change, GROWTH_RATE_CLAMP_PERCENT),
    )
    return (clamped + GROWTH_RATE_CLAMP_PERCENT) / (2 * GROWTH_RATE_CLAMP_PERCENT)
