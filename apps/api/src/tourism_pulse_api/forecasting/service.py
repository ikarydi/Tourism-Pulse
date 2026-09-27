"""Build monthly panels from stored signals, forecast them, store the result.

Pools share coefficients (see model.py):

- countries: nights plus Wikipedia and GDELT attention (the model Gate 2
  validated),
- regions and KSH destinations: nights only (no attention series; not
  validated at this level, so shown without a track record).

NUTS 3 areas have two years of monthly data, too short to forecast.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Forecast, Place, Signal
from tourism_pulse_api.db.models.forecast import BACKTEST, LIVE
from tourism_pulse_api.forecasting import model

SIGNAL_TYPE = "tourism_nights"
# Sources reporting a unit other than nights (KSH: thousands of nights).
UNIT_FACTORS = {"thousand_nights": 1000.0}
ATTENTION_SIGNALS = {
    "wiki": "wikipedia_views_monthly",
    "gdelt": "gdelt_tourism_share",
    "tone": "gdelt_tourism_tone",
}
# Pool -> (place types, models in order of preference). Only the country
# pool was validated with attention (Gate 2); the others use nights alone.
POOLS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "countries": (("country",), ("POOL_GR_WG", "POOL_GR_W", "POOL_GR")),
    "regions": (("region", "destination"), ("POOL_GR",)),
}
_BATCH_ROWS = 1000


def month_end(period: pd.Period) -> datetime:
    return datetime(period.year, period.month, monthrange(period.year, period.month)[1], tzinfo=UTC)


def _monthly(rows) -> dict[int, pd.Series]:
    """place id -> monthly series; sources reporting the same month are averaged."""
    values: dict[int, dict[pd.Period, list[float]]] = defaultdict(lambda: defaultdict(list))
    for place_id, observed_at, value, unit in rows:
        factor = UNIT_FACTORS.get(unit or "", 1.0)
        values[place_id][pd.Period(observed_at, "M")].append(float(value) * factor)
    return {
        place_id: pd.Series({month: sum(v) / len(v) for month, v in months.items()}).sort_index()
        for place_id, months in values.items()
    }


def load_panel(db: Session, place_types: tuple[str, ...]) -> dict[int, pd.DataFrame]:
    """place id -> monthly frame with y (nights) and any attention series."""
    place_ids = [
        place_id for (place_id,) in db.query(Place.id).filter(Place.place_type.in_(place_types))
    ]
    if not place_ids:
        return {}

    def series(signal_type: str) -> dict[int, pd.Series]:
        rows = (
            db.query(Signal.place_id, Signal.observed_at, Signal.value, Signal.unit)
            .filter(Signal.signal_type == signal_type, Signal.place_id.in_(place_ids))
            .all()
        )
        return _monthly(rows)

    nights = series(SIGNAL_TYPE)
    attention = {column: series(signal_type) for column, signal_type in ATTENTION_SIGNALS.items()}
    panel = {}
    for place_id, y in nights.items():
        frame = pd.DataFrame({"y": y})
        for column, by_place in attention.items():
            if place_id in by_place:
                frame = frame.join(by_place[place_id].rename(column), how="outer")
        index = pd.period_range(frame.index.min(), frame.index.max(), freq="M")
        panel[place_id] = frame.reindex(index)
    return panel


def forecast_rows(forecasts: list[model.Forecast], *, kind: str, issued_at: datetime) -> list[dict]:
    return [
        {
            "place_id": forecast.key,
            "signal_type": SIGNAL_TYPE,
            "kind": kind,
            "model": forecast.model,
            "issued_at": issued_at,
            "origin": month_end(forecast.origin),
            "target": month_end(forecast.target),
            "horizon": forecast.horizon,
            "point": round(forecast.point, 2),
            "low_80": round(forecast.low_80, 2),
            "high_80": round(forecast.high_80, 2),
            "low_95": round(forecast.low_95, 2),
            "high_95": round(forecast.high_95, 2),
        }
        for forecast in forecasts
    ]


def store(db: Session, rows: list[dict], *, kind: str) -> None:
    """Live forecasts are written once and kept (the track record);
    backtest forecasts are replaced when recomputed."""
    for start in range(0, len(rows), _BATCH_ROWS):
        statement = insert(Forecast).values(rows[start : start + _BATCH_ROWS])
        if kind == LIVE:
            statement = statement.on_conflict_do_nothing(
                constraint="uq_forecasts_place_type_kind_origin_target"
            )
        else:
            statement = statement.on_conflict_do_update(
                constraint="uq_forecasts_place_type_kind_origin_target",
                set_={
                    column: getattr(statement.excluded, column)
                    for column in (
                        "model",
                        "issued_at",
                        "point",
                        "low_80",
                        "high_80",
                        "low_95",
                        "high_95",
                        "horizon",
                    )
                },
            )
        db.execute(statement)


def run_live(db: Session, *, now: datetime | None = None) -> int:
    issued_at = now or datetime.now(UTC)
    rows = []
    for place_types, models in POOLS.values():
        panel = load_panel(db, place_types)
        forecasts = model.forecast_pool(panel, models=models)
        rows += forecast_rows(forecasts, kind=LIVE, issued_at=issued_at)
    store(db, rows, kind=LIVE)
    return len(rows)


def run_backtest(db: Session, first: pd.Period, last: pd.Period) -> int:
    """What the method would have issued at each origin from `first` to
    `last`, from the data known then (countries only: the validated pool)."""
    place_types, models = POOLS["countries"]
    panel = load_panel(db, place_types)
    issued_at = datetime.now(UTC)
    rows = []
    for origin in pd.period_range(first, last, freq="M"):
        rows += forecast_rows(
            model.forecast_pool(model.as_of(panel, origin), models=models),
            kind=BACKTEST,
            issued_at=issued_at,
        )
    store(db, rows, kind=BACKTEST)
    return len(rows)
