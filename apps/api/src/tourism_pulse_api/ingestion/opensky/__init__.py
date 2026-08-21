"""OpenSky Network airborne-traffic ingestion - free, no key required for
anonymous (lower-quota) access, unlike most other real sources this
project uses.

OpenSky's license is explicitly non-commercial - "the moment your
project becomes a product, you're out of bounds" (their own FAQ wording).
This is fine while Tourism Pulse remains a research/development project;
revisit before any commercial use.

Queries a caller-supplied bounding box (lamin/lomin/lamax/lomax) around a
destination/airport and counts currently-airborne aircraft within it as
a live transport-activity proxy - see service.py and
pulse.airport_traffic for the caveats on what this count actually means.
"""
