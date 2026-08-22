"""Normalizes a PM2.5 concentration (µg/m³) into a 0-1 Pulse Engine
input for the `environment` dimension.

Like pulse.disaster_risk, this inverts polarity on purpose: every Pulse
dimension is "higher = stronger/healthier tourism conditions", so a
HIGH PM2.5 reading (worse air quality) must produce a LOW normalized
value, not a high one. Uses the US EPA's PM2.5 breakpoints as anchors -
at/below "Good" is full marks, at/above "Unhealthy" is zero, linear
between the two. Considered anchors, not hard safety limits; revisit
once real destinations' readings are observed.
"""

# EPA AQI "Good" category ceiling for PM2.5 (µg/m³, 24-hour).
GOOD_PM25_THRESHOLD = 12.0
# EPA AQI "Unhealthy" category floor for PM2.5 (µg/m³, 24-hour).
UNHEALTHY_PM25_THRESHOLD = 55.4


def normalize_pm25(value: float) -> float:
    if value <= GOOD_PM25_THRESHOLD:
        return 1.0

    if value >= UNHEALTHY_PM25_THRESHOLD:
        return 0.0

    span = UNHEALTHY_PM25_THRESHOLD - GOOD_PM25_THRESHOLD
    return 1.0 - ((value - GOOD_PM25_THRESHOLD) / span)
