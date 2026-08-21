from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, Signal
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.signal import SignalCreate, SignalRead

router = APIRouter(
    prefix="/places/{place_id}/signals",
    tags=["signals"],
)


@router.post(
    "",
    response_model=SignalRead,
    status_code=201,
)
def create_signal(
    place_id: int,
    payload: SignalCreate,
    db: Session = Depends(get_db),
) -> Signal:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    signal = Signal(
        place_id=place_id,
        signal_type=payload.signal_type,
        value=payload.value,
        unit=payload.unit,
        observed_at=payload.observed_at,
        source=payload.source,
        source_url=payload.source_url,
    )

    db.add(signal)
    db.commit()
    db.refresh(signal)

    return signal


@router.get(
    "",
    response_model=list[SignalRead],
)
def list_signals(
    place_id: int,
    db: Session = Depends(get_db),
) -> list[Signal]:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    return (
        db.query(Signal)
        .filter(Signal.place_id == place_id)
        .order_by(Signal.observed_at.desc(), Signal.id.desc())
        .all()
    )
