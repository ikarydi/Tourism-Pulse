from datetime import UTC, datetime, timedelta
from functools import partial

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Event, Place, PulseSnapshot, Signal
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.pulse.anomaly import detect_anomaly
from tourism_pulse_api.pulse.engine import PulseEngine
from tourism_pulse_api.pulse.event_adapter import event_to_signal
from tourism_pulse_api.pulse.insights import build_all_dimension_evidence
from tourism_pulse_api.pulse.interpretation import interpret_pulse
from tourism_pulse_api.pulse.seasonal_signal_adapter import (
    SEASONAL_SIGNAL_TYPES,
    process_seasonal_signal,
)
from tourism_pulse_api.pulse.signal_normalization import SIGNAL_NORMALIZERS
from tourism_pulse_api.pulse.signal_processing import process_signal
from tourism_pulse_api.pulse.source_registry import (
    get_source_reliability as get_registry_source_reliability,
)
from tourism_pulse_api.pulse.trend_analysis import analyze_trend
from tourism_pulse_api.schemas.pulse import (
    DimensionEvidenceRead,
    PulseConfidenceRead,
    PulseDimensionsRead,
    PulseInterpretationRead,
    PulseRead,
    PulseTrendRead,
)
from tourism_pulse_api.schemas.pulse_anomaly import PulseAnomalyRead
from tourism_pulse_api.schemas.pulse_history import (
    PulseSnapshotRead,
)
from tourism_pulse_api.schemas.pulse_trend import (
    PulseTrendAnalysisRead,
    PulseTrendDriversRead,
)

router = APIRouter(
    prefix="/places/{place_id}/pulse",
    tags=["pulse"],
)


@router.get(
    "",
    response_model=PulseRead,
)
def calculate_place_pulse(
    place_id: int,
    persist: bool = True,
    db: Session = Depends(get_db),
) -> PulseRead:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    signals = (
        db.query(Signal)
        .filter(Signal.place_id == place_id)
        .order_by(Signal.observed_at.desc(), Signal.id.desc())
        .all()
    )

    events = (
        db.query(Event)
        .filter(Event.place_id == place_id)
        .order_by(Event.start_at.desc(), Event.id.desc())
        .all()
    )

    now = datetime.now(UTC)

    seasonal_signals_by_type: dict[str, list[Signal]] = {}
    other_signals = []

    for signal in signals:
        signal_type = signal.signal_type.strip().lower()

        if signal_type in SEASONAL_SIGNAL_TYPES:
            seasonal_signals_by_type.setdefault(signal_type, []).append(signal)
        elif signal_type in SIGNAL_NORMALIZERS:
            other_signals.append(signal)
        # Anything else is a raw-only/archival signal type (e.g. the raw
        # temperature/precipitation/wind_speed readings a weather comfort
        # score is derived from) - preserved in the database and queryable,
        # but it does not feed any Pulse dimension directly, and must not
        # fail the whole calculation the way an unconditional process_signal
        # call would.

    processed_signals = [
        process_signal(signal, now=now)
        for signal in other_signals
    ]

    processed_seasonal_signals = [
        process_seasonal_signal(
            signal,
            history=seasonal_signals_by_type[signal.signal_type.strip().lower()],
            now=now,
        )
        for signals_of_type in seasonal_signals_by_type.values()
        for signal in signals_of_type
    ]

    processed_signals.extend(
        seasonal_signal
        for seasonal_signal in processed_seasonal_signals
        if seasonal_signal is not None
    )

    processed_events = [
        event_to_signal(event, now=now)
        for event in events
    ]

    processed_signals.extend(
        event_signal
        for event_signal in processed_events
        if event_signal is not None
    )

    if not processed_signals:
        raise HTTPException(
            status_code=422,
            detail="No signals or events available for this place",
        )
    previous_snapshot = (
        db.query(PulseSnapshot)
        .filter(PulseSnapshot.place_id == place_id)
        .order_by(
            PulseSnapshot.calculated_at.desc(),
            PulseSnapshot.id.desc(),
        )
        .first()
    )

    previous_pulse = (
        previous_snapshot.pulse
        if previous_snapshot is not None
        else None
    )

    engine = PulseEngine(
        reliability_lookup=partial(get_registry_source_reliability, db),
    )
    result = engine.calculate(
        signals=processed_signals,
        previous_pulse=previous_pulse,
    )

    interpretation = interpret_pulse(
        pulse=result.pulse,
        confidence=result.confidence,
    )

    # Evidence (pulse.insights) - which signals/articles/videos/events
    # actually explain each dimension - is only computed on the real
    # persist=true calculation, same reasoning as the snapshot write
    # below: a bulk overview scan across many places shouldn't pay for
    # per-dimension NewsArticle/VideoItem queries on every single one.
    evidence = (
        build_all_dimension_evidence(
            db,
            place_id=place_id,
            pulse=result.pulse,
            signals=signals,
            events=events,
        )
        if persist
        else None
    )

    # Bulk/overview callers (e.g. a multi-destination comparison view) pass
    # persist=false so browsing many places at once doesn't flood
    # pulse_snapshots with near-duplicate rows - trend/history still read
    # from whatever snapshots already exist via previous_pulse above.
    if persist:
        snapshot = PulseSnapshot(
            place_id=place_id,
            calculated_at=now,
            pulse=result.pulse.pulse,
            demand=result.pulse.demand,
            capacity=result.pulse.capacity,
            events=result.pulse.events,
            environment=result.pulse.environment,
            risk=result.pulse.risk,
            economic=result.pulse.economic,
            confidence_score=result.confidence.score,
            confidence_coverage=result.confidence.coverage,
        )

        db.add(snapshot)
        db.commit()

    return PulseRead(
        place_id=place_id,
        pulse=result.pulse.pulse,
        dimensions=PulseDimensionsRead(
            demand=result.pulse.demand,
            capacity=result.pulse.capacity,
            events=result.pulse.events,
            environment=result.pulse.environment,
            risk=result.pulse.risk,
            economic=result.pulse.economic,
        ),
        confidence=PulseConfidenceRead(
            score=result.confidence.score,
            coverage=result.confidence.coverage,
        ),
        trend=PulseTrendRead(
            change=result.trend.change,
            direction=result.trend.direction,
        ),
        interpretation=PulseInterpretationRead(
            headline=interpretation["headline"],
            strengths=interpretation["strengths"],
            weaknesses=interpretation["weaknesses"],
            data_quality=interpretation["data_quality"],
        ),
        evidence=(
            {
                dimension: DimensionEvidenceRead.model_validate(dimension_evidence)
                for dimension, dimension_evidence in evidence.items()
            }
            if evidence is not None
            else None
        ),
    )

@router.get(
    "/history",
    response_model=list[PulseSnapshotRead],
)
def get_place_pulse_history(
    place_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
) -> list[PulseSnapshot]:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=422,
            detail="Limit must be between 1 and 100",
        )

    return (
        db.query(PulseSnapshot)
        .filter(PulseSnapshot.place_id == place_id)
        .order_by(
            PulseSnapshot.calculated_at.desc(),
            PulseSnapshot.id.desc(),
        )
        .all()
    )

@router.get(
    "/trend",
    response_model=PulseTrendAnalysisRead,
)
def get_place_pulse_trend(
    place_id: int,
    db: Session = Depends(get_db),
) -> PulseTrendAnalysisRead:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    snapshots = (
        db.query(PulseSnapshot)
        .filter(PulseSnapshot.place_id == place_id)
        .order_by(
            PulseSnapshot.calculated_at.desc(),
            PulseSnapshot.id.desc(),
        )
        .all()
    )

    if not snapshots:
        raise HTTPException(
            status_code=422,
            detail="No pulse history available for this place",
        )

    current = snapshots[0]

    now = current.calculated_at

    previous_24h = next(
        (
            snapshot
            for snapshot in snapshots[1:]
            if snapshot.calculated_at
            <= now - timedelta(hours=24)
        ),
        None,
    )

    previous_7d = next(
        (
            snapshot
            for snapshot in snapshots[1:]
            if snapshot.calculated_at
            <= now - timedelta(days=7)
        ),
        None,
    )

    result = analyze_trend(
        current=current,
        previous_24h=previous_24h,
        previous_7d=previous_7d,
    )

    return PulseTrendAnalysisRead(
        place_id=place_id,
        current_pulse=result.current_pulse,
        change_24h=result.change_24h,
        change_7d=result.change_7d,
        direction=result.direction,
        momentum=result.momentum,
        drivers=PulseTrendDriversRead(
            positive=result.positive_drivers,
            negative=result.negative_drivers,
        ),
    )
@router.get(
    "/anomaly",
    response_model=PulseAnomalyRead,
)
def get_place_pulse_anomaly(
    place_id: int,
    db: Session = Depends(get_db),
) -> PulseAnomalyRead:
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    snapshots = (
        db.query(PulseSnapshot)
        .filter(PulseSnapshot.place_id == place_id)
        .order_by(
            PulseSnapshot.calculated_at.desc(),
            PulseSnapshot.id.desc(),
        )
        .limit(2)
        .all()
    )

    if not snapshots:
        raise HTTPException(
            status_code=422,
            detail="No pulse history available for this place",
        )

    current = snapshots[0]
    previous = snapshots[1] if len(snapshots) > 1 else None

    result = detect_anomaly(
        current=current,
        previous=previous,
    )

    return PulseAnomalyRead(
        place_id=place_id,
        detected=result.detected,
        severity=result.severity,
        change=result.change,
        message=result.message,
        drivers=result.drivers,
    )