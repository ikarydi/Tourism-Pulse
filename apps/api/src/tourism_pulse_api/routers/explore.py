from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import SavedView
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.explore.ask import AskInvalidError, AskUnavailableError, ask
from tourism_pulse_api.explore.catalog import build_catalog
from tourism_pulse_api.explore.query import UnknownMetricError, resolve_places, run_query
from tourism_pulse_api.schemas.explore import (
    AskRequest,
    AskResponse,
    CatalogRead,
    MetricRead,
    PlaceRefRead,
    QueryResultRead,
    QueryRowRead,
    QuerySpec,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
)

router = APIRouter(prefix="/explore", tags=["explore"])


def _place_ref(place) -> PlaceRefRead:
    return PlaceRefRead(
        id=place.id,
        name=place.name,
        place_type=place.place_type,
        country_code=place.destination.country_code if place.destination else None,
    )


@router.get("/catalog", response_model=CatalogRead)
def get_catalog(db: Session = Depends(get_db)) -> CatalogRead:
    """Every metric a chart can use, and every place it can be filtered to."""
    return CatalogRead(
        metrics=[MetricRead(**metric.public()) for metric in build_catalog(db).values()],
        places=[_place_ref(place) for place in resolve_places(db, None, None)],
    )


@router.post("/query", response_model=QueryResultRead)
def post_query(spec: QuerySpec, db: Session = Depends(get_db)) -> QueryResultRead:
    """Combine catalog metrics on one place x time grid (long format)."""
    try:
        result = run_query(
            db,
            metric_ids=spec.metrics,
            place_ids=spec.places,
            place_type=spec.place_type,
            grain=spec.grain,
            start=spec.start,
            end=spec.end,
        )
    except UnknownMetricError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with_rows = {row.place_id for row in result.rows}
    periods = [row.period for row in result.rows if row.period is not None]
    return QueryResultRead(
        metrics=[MetricRead(**metric.public()) for metric in result.metrics],
        places=[_place_ref(place) for place in result.places if place.id in with_rows],
        rows=[QueryRowRead(**row.__dict__) for row in result.rows],
        truncated=result.truncated,
        data_through=max(periods) if periods else None,
        notes=result.notes,
    )


@router.post("/ask", response_model=AskResponse)
def post_ask(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    """Translate a question into a chart spec chosen from the catalog."""
    try:
        title, spec, explanation = ask(db, request.question)
    except AskUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AskInvalidError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AskResponse(title=title, spec=spec, explanation=explanation)


# --- saved views --------------------------------------------------------------


def _validated_metrics(db: Session, metric_ids: list[str]) -> None:
    catalog = build_catalog(db)
    unknown = [metric for metric in metric_ids if metric not in catalog]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown metric(s): {', '.join(unknown)}")


def _get_view(db: Session, view_id: int) -> SavedView:
    view = db.get(SavedView, view_id)
    if view is None:
        raise HTTPException(status_code=404, detail="View not found")
    return view


@router.get("/views", response_model=list[SavedViewRead])
def list_views(db: Session = Depends(get_db)) -> list[SavedView]:
    return db.query(SavedView).order_by(SavedView.position, SavedView.id).all()


@router.post("/views", response_model=SavedViewRead, status_code=201)
def create_view(payload: SavedViewCreate, db: Session = Depends(get_db)) -> SavedView:
    _validated_metrics(db, payload.spec.query.metrics)
    last = db.query(SavedView.position).order_by(SavedView.position.desc()).first()
    view = SavedView(
        title=payload.title,
        description=payload.description,
        spec=payload.spec.model_dump(mode="json"),
        pinned=payload.pinned,
        position=(last[0] + 1) if last else 0,
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return view


@router.put("/views/{view_id}", response_model=SavedViewRead)
def update_view(view_id: int, payload: SavedViewUpdate, db: Session = Depends(get_db)) -> SavedView:
    view = _get_view(db, view_id)
    if payload.spec is not None:
        _validated_metrics(db, payload.spec.query.metrics)
        view.spec = payload.spec.model_dump(mode="json")
    for field in ("title", "description", "pinned", "position"):
        value = getattr(payload, field)
        if value is not None:
            setattr(view, field, value)
    db.commit()
    db.refresh(view)
    return view


@router.delete("/views/{view_id}", status_code=204)
def delete_view(view_id: int, db: Session = Depends(get_db)) -> Response:
    db.delete(_get_view(db, view_id))
    db.commit()
    return Response(status_code=204)
