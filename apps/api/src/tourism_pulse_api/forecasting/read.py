"""Read forecasts back with the actuals they are scored against."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Forecast, Place, Signal
from tourism_pulse_api.db.models.forecast import BACKTEST, LIVE
from tourism_pulse_api.forecasting.service import SIGNAL_TYPE, UNIT_FACTORS

# From research/forecast/results/VERDICT.md (Gate 2, 30 countries,
# targets 2025-07 .. 2026-06, horizons 1-12).
VALIDATION = {
    "study": "Gate 2 (pre-registered, holdout run once on 2026-09-27)",
    "mape": 0.0496,
    "seasonal_naive_mape": 0.0535,
    "countries_better_than_last_year": 20,
    "countries_attention_helps": 26,
    "countries": 30,
    "coverage_80": 0.81,
}
METHOD = (
    "Pooled regression per horizon on recent year-on-year growth in official nights, "
    "plus growth in Wikipedia views and in GDELT tourism news share and tone. "
    "Published as a seasonal outlook: it beat last year's figure in 20 of 30 countries "
    "in the backtest, by 7% at the median, which is short of the pre-registered claim."
)
UNVALIDATED = (
    "Nights only, no attention data. Not validated at this level: regional series start "
    "in 2020, so the track record starts with these forecasts."
)


def nights_by_place(
    db: Session, place_ids: list[int], *, since: datetime | None = None
) -> dict[int, pd.Series]:
    query = db.query(Signal.place_id, Signal.observed_at, Signal.value, Signal.unit).filter(
        Signal.signal_type == SIGNAL_TYPE, Signal.place_id.in_(place_ids)
    )
    if since is not None:
        query = query.filter(Signal.observed_at >= since)
    rows = query.all()
    grouped: dict[int, dict[pd.Period, list[float]]] = defaultdict(lambda: defaultdict(list))
    for place_id, observed_at, value, unit in rows:
        grouped[place_id][pd.Period(observed_at, "M")].append(
            float(value) * UNIT_FACTORS.get(unit or "", 1.0)
        )
    return {
        place_id: pd.Series({m: sum(v) / len(v) for m, v in months.items()}).sort_index()
        for place_id, months in grouped.items()
    }


def latest_live(db: Session, place_ids: list[int] | None = None) -> dict[int, list[Forecast]]:
    """place id -> the forecasts of its latest live origin, by horizon."""
    latest = db.query(Forecast.place_id, func.max(Forecast.origin).label("origin")).filter(
        Forecast.kind == LIVE, Forecast.signal_type == SIGNAL_TYPE
    )
    if place_ids is not None:
        latest = latest.filter(Forecast.place_id.in_(place_ids))
    latest_sub = latest.group_by(Forecast.place_id).subquery()
    rows = (
        db.query(Forecast)
        .join(
            latest_sub,
            (Forecast.place_id == latest_sub.c.place_id) & (Forecast.origin == latest_sub.c.origin),
        )
        .filter(Forecast.kind == LIVE, Forecast.signal_type == SIGNAL_TYPE)
        .order_by(Forecast.place_id, Forecast.horizon)
        .all()
    )
    out: dict[int, list[Forecast]] = defaultdict(list)
    for row in rows:
        out[row.place_id].append(row)
    return out


@dataclass
class Outlook:
    months: int
    forecast: float
    last_year: float
    change: float
    low_80: float
    high_80: float


def outlook(forecasts: list[Forecast], actuals: pd.Series, months: int) -> Outlook | None:
    """Total of the next `months` forecast months against the same months a
    year earlier. The band sums the 80% bounds, which overstates the band
    of a total; it is shown as a range, not as an interval."""
    window = [f for f in forecasts if f.horizon <= months]
    if len(window) < months:
        return None
    last_year = [actuals.get(pd.Period(f.target, "M") - 12) for f in window]
    if any(value is None or pd.isna(value) for value in last_year):
        return None
    total_ly = float(sum(last_year))
    total = float(sum(float(f.point) for f in window))
    if total_ly <= 0:
        return None
    return Outlook(
        months=months,
        forecast=total,
        last_year=total_ly,
        change=total / total_ly - 1,
        low_80=float(sum(float(f.low_80) for f in window)),
        high_80=float(sum(float(f.high_80) for f in window)),
    )


@dataclass
class Accuracy:
    scored: int
    mape: float | None
    coverage_80: float | None
    by_horizon: list[dict]


_SCORED = text(
    """
    with actual as (
        select place_id, observed_at,
               avg(value * case when unit = 'thousand_nights' then 1000 else 1 end) as value
        from signals
        where signal_type = :signal_type and place_id = any(:place_ids)
        group by place_id, observed_at
    )
    select f.place_id, f.horizon,
           count(*) as scored,
           avg(abs(a.value - f.point) / a.value) as mape,
           avg(case when a.value between f.low_80 and f.high_80 then 1.0 else 0.0 end) as coverage
    from forecasts f
    join actual a on a.place_id = f.place_id and a.observed_at = f.target
    where f.kind = :kind and f.signal_type = :signal_type
      and f.place_id = any(:place_ids) and a.value > 0
    group by f.place_id, f.horizon
    """
)


def accuracy(db: Session, place_ids: list[int], kind: str) -> dict[int, Accuracy]:
    """Scored forecasts per place: every forecast whose month now has an
    official figure. Scored in the database, per place and horizon."""
    if not place_ids:
        return {}
    rows = db.execute(
        _SCORED, {"signal_type": SIGNAL_TYPE, "place_ids": place_ids, "kind": kind}
    ).all()
    grouped: dict[int, list] = defaultdict(list)
    for row in rows:
        grouped[row.place_id].append(row)
    out = {}
    for place_id, items in grouped.items():
        scored = sum(item.scored for item in items)
        out[place_id] = Accuracy(
            scored=scored,
            mape=sum(float(item.mape) * item.scored for item in items) / scored,
            coverage_80=sum(float(item.coverage) * item.scored for item in items) / scored,
            by_horizon=[
                {"horizon": item.horizon, "mape": float(item.mape), "scored": item.scored}
                for item in sorted(items, key=lambda item: item.horizon)
            ],
        )
    return out


def place_forecast(db: Session, place: Place) -> dict | None:
    forecasts = latest_live(db, [place.id]).get(place.id)
    if not forecasts:
        return None
    actuals = nights_by_place(db, [place.id]).get(place.id, pd.Series(dtype=float))
    origin = pd.Period(forecasts[0].origin, "M")
    history = actuals[(actuals.index > origin - 36) & (actuals.index <= origin)]
    backtest = accuracy(db, [place.id], BACKTEST).get(place.id)
    live = accuracy(db, [place.id], LIVE).get(place.id)
    return {
        "place_id": place.id,
        "signal_type": SIGNAL_TYPE,
        "unit": "nights",
        "model": forecasts[0].model,
        "validated": place.place_type == "country",
        "method": METHOD if place.place_type == "country" else UNVALIDATED,
        "validation": VALIDATION if place.place_type == "country" else None,
        "issued_at": forecasts[0].issued_at,
        "origin": str(origin),
        "history": [{"period": str(m), "value": float(v)} for m, v in history.items()],
        "points": [
            {
                "period": str(pd.Period(f.target, "M")),
                "horizon": f.horizon,
                "point": float(f.point),
                "low_80": float(f.low_80),
                "high_80": float(f.high_80),
                "low_95": float(f.low_95),
                "high_95": float(f.high_95),
                "last_year": (
                    float(actuals[pd.Period(f.target, "M") - 12])
                    if (pd.Period(f.target, "M") - 12) in actuals
                    else None
                ),
            }
            for f in forecasts
        ],
        "outlook": [
            o.__dict__
            for o in (outlook(forecasts, actuals, 3), outlook(forecasts, actuals, 12))
            if o
        ],
        "backtest": backtest.__dict__ if backtest else None,
        "track_record": live.__dict__ if live else None,
    }


def scoreboard(db: Session) -> list[dict]:
    latest = latest_live(db)
    if not latest:
        return []
    place_ids = sorted(latest)
    places = {place.id: place for place in db.query(Place).filter(Place.id.in_(place_ids))}
    earliest = min(forecast.target for forecasts in latest.values() for forecast in forecasts)
    actuals = nights_by_place(db, place_ids, since=earliest - timedelta(days=400))
    backtest = accuracy(db, place_ids, BACKTEST)
    live = accuracy(db, place_ids, LIVE)
    rows = []
    for place_id, forecasts in latest.items():
        place = places[place_id]
        series = actuals.get(place_id, pd.Series(dtype=float))
        next_3 = outlook(forecasts, series, 3)
        next_12 = outlook(forecasts, series, 12)
        rows.append(
            {
                "place_id": place_id,
                "name": place.name,
                "place_type": place.place_type,
                "country_code": place.destination.country_code if place.destination else None,
                "origin": str(pd.Period(forecasts[0].origin, "M")),
                "model": forecasts[0].model,
                "validated": place.place_type == "country",
                "next_3_change": next_3.change if next_3 else None,
                "next_12_change": next_12.change if next_12 else None,
                "next_12_nights": next_12.forecast if next_12 else None,
                "backtest_mape": backtest[place_id].mape if place_id in backtest else None,
                "live_scored": live[place_id].scored if place_id in live else 0,
                "live_mape": live[place_id].mape if place_id in live else None,
            }
        )
    return rows
