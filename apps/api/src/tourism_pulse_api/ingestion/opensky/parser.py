"""Parser for the OpenSky Network `/states/all` REST endpoint.

https://openskynetwork.github.io/opensky-api/rest.html

Verified response shape:

    {"time": <unix seconds>, "states": [[...18-element array...], ...]}

Each state vector is a positional array (not an object) - index meanings
per OpenSky's own documentation:

    0 icao24, 1 callsign, 2 origin_country, 3 time_position,
    4 last_contact, 5 longitude, 6 latitude, 7 baro_altitude,
    8 on_ground, 9 velocity, 10 true_track, 11 vertical_rate,
    12 sensors, 13 geo_altitude, 14 squawk, 15 spi,
    16 position_source, 17 category

Only the indices this adapter actually uses (0, 1, 8) are named below -
the rest are intentionally left as positional, undocumented fields
rather than parsed into a full dataclass nobody needs yet.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

OPENSKY_SOURCE_NAME = "opensky"
OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"

_CALLSIGN_INDEX = 1
_ON_GROUND_INDEX = 8

# How many callsigns to keep for a human-readable preview.
_SAMPLE_CALLSIGN_COUNT = 5


@dataclass(frozen=True)
class OpenSkyAirspaceObservation:
    """One /states/all response for one bounding box, straight from
    OpenSky. `airborne_count` excludes aircraft reporting on_ground=True -
    see service.py's docstring for why."""

    retrieved_at: datetime
    airborne_count: int
    sample_callsigns: list[str]


def parse_opensky_states(text: str) -> OpenSkyAirspaceObservation:
    """Raises `ValueError` if the response is not valid JSON or is missing
    an expected field - a malformed/unexpected response must not silently
    produce a fabricated observation.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenSky response is not valid JSON: {exc}") from exc

    try:
        retrieved_at = datetime.fromtimestamp(int(payload["time"]), tz=UTC)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected OpenSky response shape: {exc}") from exc

    # "states" is null (not an empty list) when nothing is in the
    # bounding box - a legitimate "quiet airspace" result, not an error.
    states = payload.get("states") or []

    try:
        airborne_states = [state for state in states if state[_ON_GROUND_INDEX] is False]
        sample_callsigns = [
            state[_CALLSIGN_INDEX].strip()
            for state in airborne_states[:_SAMPLE_CALLSIGN_COUNT]
            if state[_CALLSIGN_INDEX]
        ]
    except (IndexError, TypeError, AttributeError) as exc:
        raise ValueError(f"Unexpected OpenSky state vector shape: {exc}") from exc

    return OpenSkyAirspaceObservation(
        retrieved_at=retrieved_at,
        airborne_count=len(airborne_states),
        sample_callsigns=sample_callsigns,
    )
