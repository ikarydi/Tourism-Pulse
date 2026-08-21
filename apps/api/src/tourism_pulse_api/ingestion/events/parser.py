"""Parser for the Ticketmaster Discovery API v2 event-search response.

https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/

The response is `{"_embedded": {"events": [...]}, "page": {...}}`. Each
event's `classifications[].segment.name` (Music, Sports, Arts & Theatre,
Film, Miscellaneous) is mapped onto this platform's existing event taxonomy
(`pulse.event_impact.EVENT_TYPE_WEIGHTS`) via `SEGMENT_TO_EVENT_TYPE`, with a
"festival" override when the genre/sub-genre mentions it - Ticketmaster
usually tags festivals as a Music genre rather than a distinct segment.
This mapping is necessarily approximate (Ticketmaster's taxonomy is not
ours); anything unrecognized falls back to "other" rather than guessing.

Events with no concrete start time (`dates.start.dateTime` missing - i.e.
date/time still "to be announced") are skipped rather than invented.
"""

import json
from dataclasses import dataclass
from datetime import datetime

TICKETMASTER_SOURCE_NAME = "ticketmaster"
DISCOVERY_API_BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

# Ticketmaster classification segment -> this platform's event_type.
# See pulse.event_impact.EVENT_TYPE_WEIGHTS for the target taxonomy.
SEGMENT_TO_EVENT_TYPE: dict[str, str] = {
    "music": "concert",
    "sports": "sport",
    "arts & theatre": "cultural",
    "film": "cultural",
    "miscellaneous": "other",
}

DEFAULT_EVENT_TYPE = "other"


@dataclass(frozen=True)
class TicketmasterEvent:
    """One event from a Ticketmaster Discovery API search, reshaped for ingestion."""

    external_id: str
    name: str
    event_type: str
    description: str | None
    start_at: datetime
    end_at: datetime | None
    source_url: str | None
    venue_name: str | None
    venue_city: str | None


def _map_event_type(classifications: list[dict]) -> str:
    """Best-effort mapping from Ticketmaster classifications to our taxonomy."""
    for classification in classifications:
        for level in ("genre", "subGenre"):
            name = (classification.get(level) or {}).get("name", "")
            if "festival" in name.lower():
                return "festival"

    for classification in classifications:
        segment_name = (classification.get("segment") or {}).get("name", "")
        mapped = SEGMENT_TO_EVENT_TYPE.get(segment_name.strip().lower())
        if mapped is not None:
            return mapped

    return DEFAULT_EVENT_TYPE


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    # Ticketmaster's dateTime fields are UTC ISO 8601 with a trailing "Z".
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_event(raw_event: dict) -> TicketmasterEvent | None:
    start_at = _parse_datetime(
        (raw_event.get("dates", {}).get("start", {}) or {}).get("dateTime")
    )

    if start_at is None:
        # Date/time not yet announced - do not invent one.
        return None

    end_at = _parse_datetime((raw_event.get("dates", {}).get("end", {}) or {}).get("dateTime"))

    classifications = raw_event.get("classifications", []) or []
    event_type = _map_event_type(classifications)

    venues = (raw_event.get("_embedded", {}) or {}).get("venues", []) or []
    venue = venues[0] if venues else {}

    return TicketmasterEvent(
        external_id=raw_event["id"],
        name=raw_event.get("name", "Untitled event"),
        event_type=event_type,
        description=raw_event.get("info") or raw_event.get("pleaseNote"),
        start_at=start_at,
        end_at=end_at,
        source_url=raw_event.get("url"),
        venue_name=venue.get("name"),
        venue_city=(venue.get("city") or {}).get("name"),
    )


def parse_ticketmaster_events(text: str) -> list[TicketmasterEvent]:
    """Parse a Ticketmaster Discovery API event-search response.

    Raises `ValueError` if the response is not valid JSON. A response with
    zero matching events (Ticketmaster omits `_embedded` entirely in that
    case) yields an empty list rather than an error.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ticketmaster response is not valid JSON: {exc}") from exc

    if "fault" in payload:
        fault = payload["fault"]
        raise ValueError(f"Ticketmaster API error: {fault.get('faultstring', fault)}")

    raw_events = (payload.get("_embedded") or {}).get("events", [])

    events = [_parse_event(raw_event) for raw_event in raw_events]

    return [event for event in events if event is not None]
