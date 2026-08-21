from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Attraction, Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.attraction import (
    AttractionCreate,
    AttractionRead,
)

router = APIRouter(
    prefix="/places/{place_id}/attractions",
    tags=["attractions"],
)


@router.post(
    "",
    response_model=AttractionRead,
    status_code=201,
)
def create_attraction(
    place_id: int,
    payload: AttractionCreate,
    db: Session = Depends(get_db),
) -> Attraction:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    attraction = Attraction(
        place_id=place_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
    )

    db.add(attraction)
    db.commit()
    db.refresh(attraction)

    return attraction


@router.get(
    "",
    response_model=list[AttractionRead],
)
def list_attractions(
    place_id: int,
    category: str | None = None,
    db: Session = Depends(get_db),
) -> list[Attraction]:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    query = db.query(Attraction).filter(Attraction.place_id == place_id)

    if category is not None:
        query = query.filter(Attraction.category == category)

    return query.order_by(Attraction.id).all()
