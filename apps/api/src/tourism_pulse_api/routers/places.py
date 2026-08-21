from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Destination, Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.place import PlaceCreate, PlaceRead

router = APIRouter(
    prefix="/destinations/{destination_id}/places",
    tags=["places"],
)


@router.post(
    "",
    response_model=PlaceRead,
    status_code=201,
)
def create_place(
    destination_id: int,
    payload: PlaceCreate,
    db: Session = Depends(get_db),
) -> Place:
    destination = db.get(Destination, destination_id)

    if destination is None:
        raise HTTPException(
            status_code=404,
            detail="Destination not found",
        )

    place = Place(
        destination_id=destination_id,
        name=payload.name,
        place_type=payload.place_type,
    )

    db.add(place)
    db.commit()
    db.refresh(place)

    return place


@router.get(
    "",
    response_model=list[PlaceRead],
)
def list_places(
    destination_id: int,
    db: Session = Depends(get_db),
) -> list[Place]:
    destination = db.get(Destination, destination_id)

    if destination is None:
        raise HTTPException(
            status_code=404,
            detail="Destination not found",
        )

    return (
        db.query(Place)
        .filter(Place.destination_id == destination_id)
        .order_by(Place.id)
        .all()
    )
