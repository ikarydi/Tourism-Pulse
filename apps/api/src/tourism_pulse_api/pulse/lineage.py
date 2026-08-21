"""Lineage: trace a Signal back to the raw evidence that produced it
(spec section 15 - "why is this number what it is").

Walks Signal -> SourceObservation -> Source, plus any DataQualityResult
rows recorded against that observation. The Pulse/Demand levels of spec
15's example chain are computed at request time, not stored, so they are
out of scope here - this covers the stored half of the chain.

No dedicated API endpoint yet (e.g.
GET /places/{place_id}/signals/{signal_id}/lineage) - this is the
query surface a future router handler would call; adding the endpoint
itself is a small follow-up, not required this round.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.data_quality_result import DataQualityResult
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.db.models.source import Source
from tourism_pulse_api.db.models.source_observation import SourceObservation


@dataclass(frozen=True)
class LineageChain:
    signal: Signal
    source_observation: SourceObservation | None
    source: Source | None
    quality_results: list[DataQualityResult]


class SignalNotFoundError(ValueError):
    pass


def explain_signal(db: Session, signal_id: int) -> LineageChain:
    signal = db.get(Signal, signal_id)

    if signal is None:
        raise SignalNotFoundError(f"Signal {signal_id} not found")

    if signal.source_observation_id is None:
        # No raw fetch behind this signal - e.g. a manually POSTed one
        # (routers/signals.py) - not a bug, just nothing further to trace.
        return LineageChain(
            signal=signal,
            source_observation=None,
            source=None,
            quality_results=[],
        )

    source_observation = db.get(SourceObservation, signal.source_observation_id)

    source = (
        db.get(Source, source_observation.source_id)
        if source_observation is not None
        else None
    )

    quality_results = (
        db.query(DataQualityResult)
        .filter(
            DataQualityResult.source_observation_id == signal.source_observation_id
        )
        .order_by(DataQualityResult.checked_at.asc())
        .all()
    )

    return LineageChain(
        signal=signal,
        source_observation=source_observation,
        source=source,
        quality_results=quality_results,
    )
