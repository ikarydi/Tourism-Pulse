from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.observatory.pressure import pressure_for_region
from tourism_pulse_api.schemas.observatory import ObservatoryRead

router = APIRouter(
    prefix="/places/{place_id}/observatory",
    tags=["observatory"],
)


@router.get("", response_model=ObservatoryRead)
def get_place_observatory(
    place_id: int,
    db: Session = Depends(get_db),
) -> ObservatoryRead:
    """Official regional tourism-pressure indicators for the place's NUTS
    region, each ranked against every European region at the same level
    (observatory.pressure)."""
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")

    if place.nuts_code is None:
        return ObservatoryRead(place_id=place_id)

    reading = pressure_for_region(db, place.nuts_code)
    return ObservatoryRead.model_validate({"place_id": place_id, **asdict(reading)})
