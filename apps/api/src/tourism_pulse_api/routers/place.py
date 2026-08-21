from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.place import PlaceRead

router = APIRouter(
    prefix="/places",
    tags=["places"],
)


@router.get(
    "/{place_id}",
    response_model=PlaceRead,
)
def get_place(
    place_id: int,
    db: Session = Depends(get_db),
) -> Place:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    return place
