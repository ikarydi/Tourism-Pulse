"""Orchestration for turning parsed Ticketmaster events into Event rows.

Idempotent upsert keyed on (source, external_id) - re-running an ingestion
for the same city never creates duplicate Event rows for an event
Ticketmaster still lists, and picks up changes (postponements, description
edits, etc.) on the ones it does.

Each event now passes through the data-quality gate (spec section 14) as
an `EventCandidate` before being written, and gets `source_observation_id`
set for lineage - closing the gap noted in commit 8c786c9 and this
package's `__main__.py`: Event has no value/unit/observed_at the way
Signal does, so the original SignalCandidate-shaped gate didn't apply to
it as-is. `EventCandidate` (data_quality.types) is the generalized
candidate shape that does - see its docstring for why `max_future_skew`
in particular needed a real, deliberate override, not a blind reuse of
SignalCandidate's.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import EventCandidate, QualityGateResult
from tourism_pulse_api.db.models.event import Event
from tourism_pulse_api.ingestion.events.parser import (
    TICKETMASTER_SOURCE_NAME,
    TicketmasterEvent,
)


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    external_id: str
    name: str
    event_type: str
    start_at: str
    end_at: str | None
    venue_name: str | None
    venue_city: str | None
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "name": self.name,
            "event_type": self.event_type,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "venue_name": self.venue_name,
            "venue_city": self.venue_city,
            "target_dimension": self.target_dimension,
        }


def build_preview(event: TicketmasterEvent) -> IngestionPreview:
    return IngestionPreview(
        source=TICKETMASTER_SOURCE_NAME,
        external_id=event.external_id,
        name=event.name,
        event_type=event.event_type,
        start_at=event.start_at.isoformat(),
        end_at=event.end_at.isoformat() if event.end_at else None,
        venue_name=event.venue_name,
        venue_city=event.venue_city,
        target_dimension="events",
    )


def upsert_event(
    db: Session,
    *,
    place_id: int,
    event: TicketmasterEvent,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Event | None, bool, QualityGateResult]:
    """Idempotently write one Ticketmaster event as an Event row, after
    passing it through the data-quality gate (spec section 14).

    Returns (event, created, gate). `event` is None and `created` is
    False when the gate rejects the candidate - the already-archived
    SourceObservation is left untouched either way (spec 12.1), only
    the Event write is skipped. Re-running this with the same external
    event and place is otherwise a no-op beyond refreshing the stored
    fields - it never creates a duplicate row for the same
    (source, external_id).
    """
    gate = run_quality_checks(
        db,
        EventCandidate(
            place_id=place_id,
            event_type=event.event_type,
            start_at=event.start_at,
            source=TICKETMASTER_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, False, gate

    existing = (
        db.query(Event)
        .filter(
            Event.source == TICKETMASTER_SOURCE_NAME,
            Event.external_id == event.external_id,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.place_id = place_id
        existing.name = event.name
        existing.event_type = event.event_type
        existing.description = event.description
        existing.start_at = event.start_at
        existing.end_at = event.end_at
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, False, gate

    row = Event(
        place_id=place_id,
        name=event.name,
        event_type=event.event_type,
        description=event.description,
        start_at=event.start_at,
        end_at=event.end_at,
        source_url=source_url,
        source=TICKETMASTER_SOURCE_NAME,
        external_id=event.external_id,
        source_observation_id=source_observation_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True, gate


def upsert_events(
    db: Session,
    *,
    place_id: int,
    events: list[TicketmasterEvent],
    source_url: str,
    source_observation_id: int | None = None,
) -> list[tuple[Event | None, bool, QualityGateResult]]:
    return [
        upsert_event(
            db,
            place_id=place_id,
            event=event,
            source_url=source_url,
            source_observation_id=source_observation_id,
        )
        for event in events
    ]
