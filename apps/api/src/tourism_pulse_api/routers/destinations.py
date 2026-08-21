from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Destination
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.destination import (
    DestinationCreate,
    DestinationRead,
)

router = APIRouter(
    prefix="/destinations",
    tags=["destinations"],
)


@router.post(
    "",
    response_model=DestinationRead,
    status_code=201,
)
def create_destination(
    payload: DestinationCreate,
    db: Session = Depends(get_db),
) -> Destination:
    destination = Destination(
        country_code=payload.country_code,
        name=payload.name,
    )

    db.add(destination)
    db.commit()
    db.refresh(destination)

    return destination


@router.get(
    "",
    response_model=list[DestinationRead],
)
def list_destinations(
    db: Session = Depends(get_db),
) -> list[Destination]:
    return db.query(Destination).order_by(Destination.id).all()
