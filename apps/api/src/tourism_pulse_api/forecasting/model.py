"""The forecast model validated in Gate 2 (research/forecast/).

Direct pooled regressions, one per horizon h = 1..12. For target month
t = o + h, where o is the last month with an official figure:

    log(y_t / y_{t-12}) = α_h + β_h·ḡ + γ_h·wiki + δ_h·gdelt + ε_h·tone

- ḡ: mean year-on-year log growth of nights over o-2 .. o,
- wiki, gdelt: mean year-on-year log growth of Wikipedia views and of
  GDELT's tourism-article share over a-2 .. a, with a = o + 1,
- tone: mean year-on-year change in GDELT tourism tone over the same months.

All places in a pool share the coefficients. A place missing an attention
series falls back to the nested model without it (POOL_GR_W, then
POOL_GR), which is what regions get. Months touched by COVID (2020-03 to
2021-12, or their year-earlier months) are left out of the fit.

Intervals are the 10/90% and 2.5/97.5% quantiles of the fit's residuals.
"""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

HORIZONS = tuple(range(1, 13))
COVID = (pd.Period("2020-03", "M"), pd.Period("2021-12", "M"))
# Attention is known one month past the last official month: national
# figures come out 6-10 weeks after the month.
ATTENTION_LEAD = 1
MODELS: dict[str, tuple[str, ...]] = {
    "POOL_GR_WG": ("gbar", "wiki", "gdelt", "tone"),
    "POOL_GR_W": ("gbar", "wiki"),
    "POOL_GR": ("gbar",),
}
QUANTILES = {"80": (0.10, 0.90), "95": (0.025, 0.975)}
MIN_ROWS_PER_COEFFICIENT = 8


@dataclass(frozen=True)
class Forecast:
    key: object
    origin: pd.Period
    target: pd.Period
    horizon: int
    model: str
    point: float
    low_80: float
    high_80: float
    low_95: float
    high_95: float


def in_covid(month: pd.Period) -> bool:
    return COVID[0] <= month <= COVID[1]


def growth(values: pd.Series, *, difference: bool = False) -> pd.Series:
    """Year-on-year change: log growth, or a plain difference for tone."""
    if difference:
        return values - values.shift(12)
    with np.errstate(divide="ignore", invalid="ignore"):
        logged = np.log(values.where(values > 0))
    return logged - logged.shift(12)


def feature_table(frame: pd.DataFrame, h: int) -> pd.DataFrame:
    """One row per target month t, built only from data known at t - h
    (and attention up to t - h + ATTENTION_LEAD)."""
    g_y = growth(frame["y"])
    table = pd.DataFrame(index=frame.index)
    table["target"] = g_y
    table["gbar"] = g_y.rolling(3).mean().shift(h)
    attention_shift = h - ATTENTION_LEAD
    for column in ("wiki", "gdelt", "tone"):
        if column in frame:
            change = growth(frame[column], difference=column == "tone")
            table[column] = change.rolling(3).mean().shift(attention_shift)
        else:
            table[column] = np.nan

    def contaminated(t: pd.Period) -> bool:
        origin, attention = t - h, t - attention_shift
        months = [t, *(origin - k for k in range(3)), *(attention - k for k in range(3))]
        return any(in_covid(m) or in_covid(m - 12) for m in months)

    table["covid"] = [contaminated(t) for t in table.index]
    return table


@dataclass(frozen=True)
class Fit:
    beta: np.ndarray
    quantiles: dict[str, tuple[float, float]]


def fit(rows: pd.DataFrame, columns: tuple[str, ...]) -> Fit | None:
    rows = rows.dropna(subset=["target", *columns])
    if len(rows) < MIN_ROWS_PER_COEFFICIENT * (len(columns) + 1):
        return None
    design = np.column_stack([np.ones(len(rows)), rows[list(columns)].to_numpy(dtype=float)])
    target = rows["target"].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(design, target, rcond=None)
    residuals = target - design @ beta
    return Fit(
        beta=beta,
        quantiles={
            level: (float(np.quantile(residuals, low)), float(np.quantile(residuals, high)))
            for level, (low, high) in QUANTILES.items()
        },
    )


def forecast_pool(
    panel: dict[object, pd.DataFrame],
    *,
    models: tuple[str, ...] = tuple(MODELS),
) -> list[Forecast]:
    """Forecasts 1-12 months past each series' last official month.

    `panel` maps a key to a monthly frame (PeriodIndex) with column "y"
    (nights) and optionally "wiki", "gdelt" and "tone". Every frame must
    already be cut to what was known at forecast time: the fit uses all
    rows whose target is observed."""
    frames = {}
    origins = {}
    for key, frame in panel.items():
        observed = frame["y"].dropna()
        if len(observed) < 15:
            continue
        origin = observed.index.max()
        index = pd.period_range(frame.index.min(), origin + max(HORIZONS), freq="M")
        frames[key] = frame.reindex(index)
        origins[key] = origin

    forecasts: list[Forecast] = []
    for h in HORIZONS:
        tables = {key: feature_table(frame, h) for key, frame in frames.items()}
        pooled = pd.concat(tables.values(), axis=0)
        pooled = pooled[~pooled["covid"]]
        fits = {model: fit(pooled, MODELS[model]) for model in models}
        for key, table in tables.items():
            origin = origins[key]
            target = origin + h
            base = frames[key]["y"].get(target - 12)
            if base is None or pd.isna(base) or base <= 0:
                continue
            row = table.loc[target]
            if row["covid"]:
                continue
            for model in models:
                model_fit = fits[model]
                columns = MODELS[model]
                if model_fit is None or row[list(columns)].isna().any():
                    continue
                predicted = model_fit.beta[0] + float(
                    np.dot(model_fit.beta[1:], row[list(columns)].to_numpy(dtype=float))
                )
                low_80, high_80 = model_fit.quantiles["80"]
                low_95, high_95 = model_fit.quantiles["95"]
                forecasts.append(
                    Forecast(
                        key=key,
                        origin=origin,
                        target=target,
                        horizon=h,
                        model=model,
                        point=base * math.exp(predicted),
                        low_80=base * math.exp(predicted + low_80),
                        high_80=base * math.exp(predicted + high_80),
                        low_95=base * math.exp(predicted + low_95),
                        high_95=base * math.exp(predicted + high_95),
                    )
                )
                break
    return forecasts


def as_of(panel: dict[object, pd.DataFrame], origin: pd.Period) -> dict[object, pd.DataFrame]:
    """The panel as it was when `origin` was the last official month:
    nights up to the origin, attention up to origin + ATTENTION_LEAD. Series
    without a figure for the origin itself are left out."""
    cut = {}
    for key, frame in panel.items():
        if pd.isna(frame["y"].get(origin)):
            continue
        frame = frame[frame.index <= origin + ATTENTION_LEAD].copy()
        frame.loc[frame.index > origin, "y"] = np.nan
        cut[key] = frame
    return cut
