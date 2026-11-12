from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from tourism_pulse_api.briefs import build_brief, render_html
from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db

router = APIRouter(tags=["briefs"])


def _place(db: Session, place_id: int) -> Place:
    place = db.get(Place, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return place


@router.get("/places/{place_id}/brief")
def get_brief(place_id: int, db: Session = Depends(get_db)) -> dict:
    """The Destination Pressure Brief as data. Paid content: refused in
    public mode (tourism_pulse_api.public)."""
    return asdict(build_brief(db, _place(db, place_id)))


@router.get("/places/{place_id}/brief.html", response_class=HTMLResponse)
def get_brief_html(
    place_id: int, licensee: str | None = None, db: Session = Depends(get_db)
) -> HTMLResponse:
    """The brief laid out for print (A4)."""
    return HTMLResponse(render_html(build_brief(db, _place(db, place_id)), licensee=licensee))
