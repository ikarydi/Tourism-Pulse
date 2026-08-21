"""No parser exists yet - there is no real Airbnb payload to parse (see
client.py). This dataclass sketches the shape a future adapter would
likely produce, inferred from the master spec's accommodation-statistics
entities (spec sections 6.3, 11.2) - it is explicitly unverified against
any real API response, so no `parse_*` function is defined here. Writing
one now would mean inventing parsing logic for data nobody has seen,
which is worse than not having a parser at all.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AirbnbObservation:
    """Shape unverified - sketched from spec 6.3/11.2, not a real payload."""

    period: date
    place_name: str
    active_listing_count: int
    average_nightly_price: float
    average_occupancy_rate: float | None
