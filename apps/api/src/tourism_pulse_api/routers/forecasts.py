import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.forecasting.read import place_forecast, scoreboard
from tourism_pulse_api.schemas.forecast import ForecastSummaryRead, PlaceForecastRead

router = APIRouter(tags=["forecasts"])

# The scoreboard changes only when forecasts are issued or Eurostat
# publishes a month; a short cache keeps page loads quick.
_SCOREBOARD_TTL_SECONDS = 300
_scoreboard: dict[str, object] = {}


@router.get("/places/{place_id}/forecast", response_model=PlaceForecastRead)
def get_place_forecast(place_id: int, db: Session = Depends(get_db)) -> PlaceForecastRead:
    """The latest live forecast of monthly nights, with its history, the
    backtest accuracy and the live track record."""
    place = db.get(Place, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    forecast = place_forecast(db, place)
    if forecast is None:
        raise HTTPException(status_code=404, detail="No forecast for this place")
    return PlaceForecastRead.model_validate(forecast)


@router.get("/forecasts", response_model=list[ForecastSummaryRead])
def list_forecasts(db: Session = Depends(get_db)) -> list[ForecastSummaryRead]:
    """Every place with a live forecast: outlook against last year and accuracy."""
    cached_at = _scoreboard.get("at")
    if not isinstance(cached_at, float) or time.time() - cached_at > _SCOREBOARD_TTL_SECONDS:
        _scoreboard["rows"] = [ForecastSummaryRead.model_validate(row) for row in scoreboard(db)]
        _scoreboard["at"] = time.time()
    rows = _scoreboard["rows"]
    assert isinstance(rows, list)
    return rows
