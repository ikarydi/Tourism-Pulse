"""Thin HTTP wrappers around pulse.lineage.explain_signal/explain_event
(spec section 15 - "why is this number what it is") - their first caller;
neither had any route before this.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.pulse.lineage import (
    EventLineageChain,
    EventNotFoundError,
    LineageChain,
    SignalNotFoundError,
    explain_event,
    explain_signal,
)
from tourism_pulse_api.schemas.lineage import (
    EventLineageRead,
    LineageQualityResultRead,
    LineageSourceObservationRead,
    LineageSourceRead,
    SignalLineageRead,
)

router = APIRouter(
    prefix="/places/{place_id}",
    tags=["lineage"],
)


def _require_place(db: Session, place_id: int) -> None:
    if db.get(Place, place_id) is None:
        raise HTTPException(status_code=404, detail="Place not found")


def _to_signal_lineage_read(chain: LineageChain) -> SignalLineageRead:
    return SignalLineageRead(
        signal_id=chain.signal.id,
        place_id=chain.signal.place_id,
        signal_type=chain.signal.signal_type,
        value=chain.signal.value,
        unit=chain.signal.unit,
        source=chain.signal.source,
        observed_at=chain.signal.observed_at,
        source_observation=(
            LineageSourceObservationRead.model_validate(chain.source_observation)
            if chain.source_observation is not None
            else None
        ),
        source_detail=(
            LineageSourceRead.model_validate(chain.source) if chain.source is not None else None
        ),
        quality_results=[
            LineageQualityResultRead.model_validate(result) for result in chain.quality_results
        ],
    )


def _to_event_lineage_read(chain: EventLineageChain) -> EventLineageRead:
    return EventLineageRead(
        event_id=chain.event.id,
        place_id=chain.event.place_id,
        name=chain.event.name,
        event_type=chain.event.event_type,
        source=chain.event.source,
        start_at=chain.event.start_at,
        source_observation=(
            LineageSourceObservationRead.model_validate(chain.source_observation)
            if chain.source_observation is not None
            else None
        ),
        source_detail=(
            LineageSourceRead.model_validate(chain.source) if chain.source is not None else None
        ),
        quality_results=[
            LineageQualityResultRead.model_validate(result) for result in chain.quality_results
        ],
    )


@router.get(
    "/signals/{signal_id}/lineage",
    response_model=SignalLineageRead,
)
def get_signal_lineage(
    place_id: int,
    signal_id: int,
    db: Session = Depends(get_db),
) -> SignalLineageRead:
    _require_place(db, place_id)

    try:
        chain = explain_signal(db, signal_id)
    except SignalNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Signal not found") from exc

    if chain.signal.place_id != place_id:
        raise HTTPException(status_code=404, detail="Signal not found for this place")

    return _to_signal_lineage_read(chain)


@router.get(
    "/events/{event_id}/lineage",
    response_model=EventLineageRead,
)
def get_event_lineage(
    place_id: int,
    event_id: int,
    db: Session = Depends(get_db),
) -> EventLineageRead:
    _require_place(db, place_id)

    try:
        chain = explain_event(db, event_id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Event not found") from exc

    if chain.event.place_id != place_id:
        raise HTTPException(status_code=404, detail="Event not found for this place")

    return _to_event_lineage_read(chain)
