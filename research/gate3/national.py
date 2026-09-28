"""Gate 3 Part 2 (descriptive): national visitor series, one country each.

    python -m research.gate3.national

As PREREGISTRATION.md: for each country with a retrieved series (Spain
only, see data/NATIONAL.md), two regressions per horizon fitted on that
country's rows alone, WG's regressors with and without the year-on-year log
growth of the national series at its information date; the MASE ratio at
h <= 3 on development and holdout. Spain's FRONTUR is known at o + 1.
"""

import math

import numpy as np
import pandas as pd

from research.forecast.backtest import HORIZONS, PERIODS, SCALE_WINDOW, regression, table_lines
from research.gate3.backtest import BASE, DATA_DIR, DECISION_HORIZONS, RESULTS_DIR, gate3_panel
from research.gate3.backtest import feature_table as gate3_features
from research.nowcast.backtest import common_sample

INFORMATION_LEAD = {"ES": 1}  # months after the origin the series is known


def national_growth() -> dict[str, pd.Series]:
    table = pd.read_csv(DATA_DIR / "national.csv")
    out = {}
    for geo, block in table.groupby("geo"):
        values = block.set_index(pd.PeriodIndex(block["month"], freq="M"))["value"].astype(float)
        full = values.reindex(pd.period_range(values.index.min(), values.index.max(), freq="M"))
        logged = np.log(full.where(full > 0))
        out[str(geo)] = logged - logged.shift(12)
    return out


def run(geo: str, frame: pd.DataFrame, growth: pd.Series, period: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["nat"] = growth.reindex(frame.index)
    lead = INFORMATION_LEAD[geo]
    start, end = PERIODS[period]
    models = {"OWN": BASE, "OWN_NAT": (*BASE, "nat")}
    records = []
    for h in HORIZONS:
        table = gate3_features(frame, h)
        table["nat"] = frame["nat"].shift(h - lead)
        for t in pd.period_range(start, end, freq="M"):
            origin = t - h
            actual, base = frame["y"].get(t), frame["y"].get(t - 12)
            if pd.isna(actual) or pd.isna(base) or pd.isna(frame["y"].get(origin)):
                continue
            row = table.loc[t]
            if row["covid"]:
                continue
            train = table[(table.index <= origin) & ~table["covid"]]
            for model, columns in models.items():
                forecast = regression(train, row, columns, base)
                if forecast is not None:
                    records.append(
                        {
                            "geo": geo,
                            "target": str(t),
                            "h": h,
                            "model": model,
                            "actual": actual,
                            "forecast": forecast.point,
                        }
                    )
    errors = pd.DataFrame(records)
    y = frame["y"]
    scale = y.diff(12).abs()[(y.index >= SCALE_WINDOW[0]) & (y.index <= SCALE_WINDOW[1])].mean()
    errors["scaled_abs_error"] = (errors["actual"] - errors["forecast"]).abs() / scale
    errors["ape"] = (errors["actual"] - errors["forecast"]).abs() / errors["actual"]
    return errors


def summary(errors: pd.DataFrame, horizons: tuple[int, ...]) -> tuple[float, float, float, int]:
    both = common_sample(errors[errors["h"].isin(horizons)], ("OWN", "OWN_NAT"))
    if both.empty:
        return math.nan, math.nan, math.nan, 0
    mase = both.groupby("model")["scaled_abs_error"].mean()
    ape = both.groupby("model")["ape"].mean()
    cells = len(both) // 2
    return float(mase["OWN_NAT"] / mase["OWN"]), float(ape["OWN"]), float(ape["OWN_NAT"]), cells


def main() -> None:
    panel = gate3_panel()
    growth = national_growth()
    rows, by_h = [], []
    for geo in sorted(growth):
        for period in ("dev", "holdout"):
            errors = run(geo, panel[geo], growth[geo], period)
            errors.to_csv(RESULTS_DIR / f"national_{geo}_{period}_errors.csv", index=False)
            for label, horizons in (
                ("h ≤ 3", DECISION_HORIZONS),
                ("h = 4-12", tuple(range(4, 13))),
            ):
                ratio, own, nat, cells = summary(errors, horizons)
                rows.append(
                    [geo, period, label, f"{ratio:.3f}", f"{own:.2%}", f"{nat:.2%}", str(cells)]
                )
            for h in DECISION_HORIZONS:
                ratio, own, nat, cells = summary(errors, (h,))
                by_h.append([geo, period, str(h), f"{ratio:.3f}", f"{own:.2%}", f"{nat:.2%}"])
    lines = [
        "# Gate 3 Part 2 (descriptive): national visitor series",
        "",
        "One regression per horizon on the country's own rows: OWN uses WG's regressors "
        "(recent nights growth, Wikipedia, GDELT share and tone); OWN_NAT adds the national "
        "series' year-on-year log growth at its information date (Spain's FRONTUR at o + 1). "
        "Ratio = OWN_NAT MASE / OWN MASE on the cells both forecast (below 1 = the national "
        "series helps). Greece and Italy could not be retrieved; see data/NATIONAL.md.",
        "",
        *table_lines(
            ["geo", "period", "horizons", "MASE ratio", "OWN MAPE", "OWN_NAT MAPE", "cells"], rows
        ),
        "By horizon:",
        "",
        *table_lines(["geo", "period", "h", "MASE ratio", "OWN MAPE", "OWN_NAT MAPE"], by_h),
    ]
    report = "\n".join(lines)
    (RESULTS_DIR / "national.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
