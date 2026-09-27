from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.observatory.pressure import PeerCache, pressure_for_place
from tourism_pulse_api.schemas.observatory import ObservatoryRankingRead, ObservatoryRead

router = APIRouter(tags=["observatory"])


@router.get("/places/{place_id}/observatory", response_model=ObservatoryRead)
def get_place_observatory(
    place_id: int,
    db: Session = Depends(get_db),
) -> ObservatoryRead:
    """Official regional tourism-pressure indicators for the place's
    region, each ranked against every European region at the same level
    (observatory.pressure)."""
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")

    reading = pressure_for_place(db, place)
    if reading is None:
        return ObservatoryRead(place_id=place_id)
    return ObservatoryRead.model_validate({"place_id": place_id, **asdict(reading)})


@router.get("/observatory", response_model=list[ObservatoryRankingRead])
def list_observatory(db: Session = Depends(get_db)) -> list[ObservatoryRankingRead]:
    """Every place with regional data, highest tourism pressure first."""
    cache = PeerCache()
    rows = []
    for place in db.query(Place).order_by(Place.name).all():
        reading = pressure_for_place(db, place, cache)
        if reading is None or reading.score is None:
            continue
        rows.append(
            ObservatoryRankingRead.model_validate(
                {
                    "place_id": place.id,
                    "place_name": place.name,
                    "place_type": place.place_type,
                    "country_code": place.destination.country_code if place.destination else None,
                    **asdict(reading),
                }
            )
        )
    return sorted(rows, key=lambda row: row.score or 0.0, reverse=True)
