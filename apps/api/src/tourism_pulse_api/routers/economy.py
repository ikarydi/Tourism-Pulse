from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.insights.economy import economy_for_place
from tourism_pulse_api.schemas.economy import EconomyRead

router = APIRouter(tags=["economy"])


@router.get("/places/{place_id}/economy", response_model=EconomyRead)
def get_place_economy(place_id: int, db: Session = Depends(get_db)) -> EconomyRead:
    """Flights at the place's airports, and its country's hotel survey,
    prices, turnover and origin markets."""
    place = db.get(Place, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return EconomyRead.model_validate(asdict(economy_for_place(db, place)))
