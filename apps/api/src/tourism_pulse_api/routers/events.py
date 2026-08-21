from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Event, Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.event import EventCreate, EventRead

router = APIRouter(
    prefix="/places/{place_id}/events",
    tags=["events"],
)


@router.post(
    "",
    response_model=EventRead,
    status_code=201,
)
def create_event(
    place_id: int,
    payload: EventCreate,
    db: Session = Depends(get_db),
) -> Event:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    event = Event(
        place_id=place_id,
        name=payload.name,
        event_type=payload.event_type,
        description=payload.description,
        start_at=payload.start_at,
        end_at=payload.end_at,
        source_url=payload.source_url,
        source=payload.source,
        external_id=payload.external_id,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.get(
    "",
    response_model=list[EventRead],
)
def list_events(
    place_id: int,
    db: Session = Depends(get_db),
) -> list[Event]:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    return (
        db.query(Event)
        .filter(Event.place_id == place_id)
        .order_by(Event.start_at, Event.id)
        .all()
    )
