"""Lineage: trace a Signal or Event back to the raw evidence that
produced it (spec section 15 - "why is this number what it is").

Walks Signal/Event -> SourceObservation -> Source, plus any
DataQualityResult rows recorded against that observation. The
Pulse/Demand levels of spec 15's example chain are computed at request
time, not stored, so they are out of scope here - this covers the
stored half of the chain.

`explain_event` closes the gap noted in commit 8c786c9 and
ingestion.events' own module docstrings: Event now carries
`source_observation_id` too (see db/models/event.py), so it gets the
same lineage walk `explain_signal` already provided - factored into a
shared `_walk_from_source_observation` helper rather than duplicating
the SourceObservation/Source/DataQualityResult lookup logic. Kept as
two separate public functions/chain types (not one generic
`explain(db, model, id)`) since `LineageChain`/`EventLineageChain`'s
one type-specific field (`signal/event`) is what every existing caller
of `explain_signal` already depends on - a rename would be a needless
breaking change for a chain-walk that's otherwise identical.

No dedicated API endpoint yet (e.g.
GET /places/{place_id}/signals/{signal_id}/lineage) - this is the
query surface a future router handler would call; adding the endpoint
itself is a small follow-up, not required this round.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.data_quality_result import DataQualityResult
from tourism_pulse_api.db.models.event import Event
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.db.models.source import Source
from tourism_pulse_api.db.models.source_observation import SourceObservation


@dataclass(frozen=True)
class LineageChain:
    signal: Signal
    source_observation: SourceObservation | None
    source: Source | None
    quality_results: list[DataQualityResult]


@dataclass(frozen=True)
class EventLineageChain:
    event: Event
    source_observation: SourceObservation | None
    source: Source | None
    quality_results: list[DataQualityResult]


class SignalNotFoundError(ValueError):
    pass


class EventNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class _ChainParts:
    source_observation: SourceObservation | None
    source: Source | None
    quality_results: list[DataQualityResult]


def _walk_from_source_observation(
    db: Session, source_observation_id: int | None
) -> _ChainParts:
    if source_observation_id is None:
        # No raw fetch behind this record - e.g. a manually POSTed
        # signal (routers/signals.py) or manually-created event - not a
        # bug, just nothing further to trace.
        return _ChainParts(source_observation=None, source=None, quality_results=[])

    source_observation = db.get(SourceObservation, source_observation_id)

    source = (
        db.get(Source, source_observation.source_id)
        if source_observation is not None
        else None
    )

    quality_results = (
        db.query(DataQualityResult)
        .filter(DataQualityResult.source_observation_id == source_observation_id)
        .order_by(DataQualityResult.checked_at.asc())
        .all()
    )

    return _ChainParts(
        source_observation=source_observation,
        source=source,
        quality_results=quality_results,
    )


def explain_signal(db: Session, signal_id: int) -> LineageChain:
    signal = db.get(Signal, signal_id)

    if signal is None:
        raise SignalNotFoundError(f"Signal {signal_id} not found")

    parts = _walk_from_source_observation(db, signal.source_observation_id)

    return LineageChain(
        signal=signal,
        source_observation=parts.source_observation,
        source=parts.source,
        quality_results=parts.quality_results,
    )


def explain_event(db: Session, event_id: int) -> EventLineageChain:
    event = db.get(Event, event_id)

    if event is None:
        raise EventNotFoundError(f"Event {event_id} not found")

    parts = _walk_from_source_observation(db, event.source_observation_id)

    return EventLineageChain(
        event=event,
        source_observation=parts.source_observation,
        source=parts.source,
        quality_results=parts.quality_results,
    )
