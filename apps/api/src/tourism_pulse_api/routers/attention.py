import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.insights.attention import attention_for_place, attention_overview
from tourism_pulse_api.schemas.attention import AttentionRead, AttentionSummaryRead

router = APIRouter(tags=["attention"])

# The overview scans every curated place; its inputs change daily at most.
_OVERVIEW_TTL_SECONDS = 600
_overview: dict[str, object] = {}


@router.get("/places/{place_id}/attention", response_model=AttentionRead)
def get_place_attention(place_id: int, db: Session = Depends(get_db)) -> AttentionRead:
    """Wikipedia and GDELT insights for one curated place."""
    place = db.get(Place, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return AttentionRead.model_validate(asdict(attention_for_place(db, place)))


@router.get("/attention", response_model=list[AttentionSummaryRead])
def list_attention(db: Session = Depends(get_db)) -> list[AttentionSummaryRead]:
    """One attention summary per curated place."""
    cached_at = _overview.get("at")
    if not isinstance(cached_at, float) or time.time() - cached_at > _OVERVIEW_TTL_SECONDS:
        _overview["rows"] = attention_overview(db)
        _overview["at"] = time.time()
    rows = _overview["rows"]
    assert isinstance(rows, list)
    return [AttentionSummaryRead.model_validate(row) for row in rows]
