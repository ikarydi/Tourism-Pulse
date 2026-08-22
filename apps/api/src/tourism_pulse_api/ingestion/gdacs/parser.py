"""Parser for the GDACS `geteventlist/SEARCH` GeoJSON response.

https://www.gdacs.org/gdacsapi/swagger/index.html

An empty `features` list is a valid result (no current disaster alerts
for the requested country) - not an error, the same way OpenSky's empty
airspace and Wikipedia's zero-view article aren't ones.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

GDACS_SOURCE_NAME = "gdacs"
GDACS_EVENTS_BASE_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"


@dataclass(frozen=True)
class GdacsEvent:
    """One disaster-alert event, straight from GDACS."""

    event_type: str
    event_name: str
    alert_level: str
    alert_score: float
    country: str
    is_current: bool


@dataclass(frozen=True)
class GdacsEventsObservation:
    """One `geteventlist/SEARCH` response for one country filter."""

    country: str
    events: list[GdacsEvent]
    max_current_alert_score: float
    retrieved_at: datetime


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def parse_gdacs_events(text: str, *, country: str) -> GdacsEventsObservation:
    """Parse a GDACS `geteventlist/SEARCH` GeoJSON response.

    Raises `ValueError` if the response is not valid JSON or is missing
    an expected field - a malformed/unexpected response must not
    silently produce a fabricated observation.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GDACS response is not valid JSON: {exc}") from exc

    try:
        events = [
            GdacsEvent(
                event_type=feature["properties"]["eventtype"],
                event_name=feature["properties"]["eventname"],
                alert_level=feature["properties"]["alertlevel"],
                alert_score=float(feature["properties"]["alertscore"]),
                country=feature["properties"]["country"],
                is_current=_parse_bool(feature["properties"]["iscurrent"]),
            )
            for feature in payload.get("features", [])
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected GDACS response shape: {exc}") from exc

    current_scores = [event.alert_score for event in events if event.is_current]
    max_current_alert_score = max(current_scores, default=0.0)

    if max_current_alert_score < 0.0:
        raise ValueError(
            f"GDACS reported a negative alert score: {max_current_alert_score}"
        )

    return GdacsEventsObservation(
        country=country,
        events=events,
        max_current_alert_score=max_current_alert_score,
        retrieved_at=datetime.now(UTC),
    )
