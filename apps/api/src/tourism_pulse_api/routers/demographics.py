from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, PlaceDemographics
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.place_demographics import PlaceDemographicsRead

router = APIRouter(
    prefix="/places/{place_id}/demographics",
    tags=["demographics"],
)


@router.get(
    "",
    response_model=list[PlaceDemographicsRead],
)
def list_place_demographics(
    place_id: int,
    db: Session = Depends(get_db),
) -> list[PlaceDemographics]:
    """Population by year (see ingestion.eurostat.service.upsert_population)
    - reference data, not a Signal (db/models/place_demographics.py), so it
    gets its own read-only endpoint rather than living under /signals.
    """
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    return (
        db.query(PlaceDemographics)
        .filter(PlaceDemographics.place_id == place_id)
        .order_by(PlaceDemographics.year)
        .all()
    )
