"""Ticketmaster Discovery API events ingestion.

https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/

Requires a free Ticketmaster API key (TICKETMASTER_API_KEY). Maps
Ticketmaster's classification segments onto this platform's existing
event_type taxonomy so ingested events flow straight through the existing
`pulse.event_adapter` -> `events` dimension pathway, unchanged.
"""

from tourism_pulse_api.ingestion.events.parser import (
    TICKETMASTER_SOURCE_NAME,
    TicketmasterEvent,
    parse_ticketmaster_events,
)

__all__ = [
    "TICKETMASTER_SOURCE_NAME",
    "TicketmasterEvent",
    "parse_ticketmaster_events",
]
