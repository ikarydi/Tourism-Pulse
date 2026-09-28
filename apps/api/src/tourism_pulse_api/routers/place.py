from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Destination, Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.place import PlaceRead, PlaceSummaryRead

router = APIRouter(
    prefix="/places",
    tags=["places"],
)


@router.get("", response_model=list[PlaceSummaryRead])
def list_all_places(db: Session = Depends(get_db)) -> list[PlaceSummaryRead]:
    """Every place (curated destinations, countries, and the EU regions,
    areas and cities generated from official geography) in one response."""
    rows = (
        db.query(Place, Destination.country_code)
        .join(Destination, Destination.id == Place.destination_id)
        .order_by(Place.name)
        .all()
    )
    return [
        PlaceSummaryRead(
            id=place.id,
            name=place.name,
            place_type=place.place_type,
            destination_id=place.destination_id,
            country_code=country_code,
            latitude=place.latitude,
            longitude=place.longitude,
            nuts_code=place.nuts_code,
            nuts3_code=place.nuts3_code,
            urau_code=place.urau_code,
        )
        for place, country_code in rows
    ]


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
