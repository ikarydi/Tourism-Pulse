"""Rolling-origin nowcast backtest for Gate 1. See PREREGISTRATION.md.

Run from the repo root, development first:

    python -m research.nowcast.backtest --period dev

then, once the primary model is chosen and committed, exactly once:

    python -m research.nowcast.backtest --period holdout \\
        --primary POOL_W --baseline AIRLINE

Results go to research/nowcast/results/.
"""

import os

# One BLAS thread per process: the SARIMA fits run in a process pool, and
# multi-threaded BLAS inside each worker oversubscribes the CPU badly.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import math  # noqa: E402
import warnings  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"

HORIZONS = (1, 2, 3)
COVID = (pd.Period("2020-03", "M"), pd.Period("2021-12", "M"))
SCALE_WINDOW = (pd.Period("2016-01", "M"), pd.Period("2019-12", "M"))
PERIODS = {
    "dev": (pd.Period("2023-07", "M"), pd.Period("2025-06", "M")),
    "holdout": (pd.Period("2025-07", "M"), pd.Period("2026-06", "M")),
}
BASELINES = ("SN", "SNG", "AIRLINE", "GR")
ALT_MODELS = ("GR_W", "GR_WG", "POOL_W", "POOL_WG")
MODELS = BASELINES + ALT_MODELS
INTERVAL_Q = (0.10, 0.90)

# Regressors per model (all regressions also get an intercept).
REGRESSORS: dict[str, tuple[str, ...]] = {
    "GR": ("dbar_y",),
    "GR_W": ("dbar_y", "dwiki"),
    "GR_WG": ("dbar_y", "dwiki", "dgdelt", "dtone"),
    "POOL_W": ("dbar_y", "dwiki"),
    "POOL_WG": ("dbar_y", "dwiki", "dgdelt", "dtone"),
}


def in_covid(month: pd.Period) -> bool:
    return COVID[0] <= month <= COVID[1]


def load_panel(gdelt_file: str = "gdelt.csv") -> dict[str, pd.DataFrame]:
    nights = pd.read_csv(DATA_DIR / "nights.csv")
    views = pd.read_csv(DATA_DIR / "pageviews.csv")
    gdelt_path = DATA_DIR / gdelt_file
    # GDELT's API is slow to backfill; without it the GDELT models simply
    # produce no forecasts (useful for pipeline checks, never for selection).
    gdelt = (
        pd.read_csv(gdelt_path)
        if gdelt_path.exists()
        else pd.DataFrame(columns=["geo", "month", "articles", "corpus", "tone"])
    )

    wiki = views.groupby(["geo", "month"], as_index=False)["views"].sum()
    # A month is only usable if all three article series report it.
    counts = views.groupby(["geo", "month"])["series"].nunique().rename("n_series")
    wiki = wiki.merge(counts.reset_index(), on=["geo", "month"])
    wiki.loc[wiki["n_series"] < 3, "views"] = np.nan

    gdelt["gshare"] = gdelt["articles"] / gdelt["corpus"]
    # Zero-article months have no defined share growth or tone.
    gdelt.loc[gdelt["articles"] <= 0, ["gshare", "tone"]] = np.nan

    index = pd.period_range("2014-01", "2026-09", freq="M")
    panel = {}
    for geo in sorted(nights["geo"].unique()):
        frame = pd.DataFrame(index=index)
        for source, column, name in (
            (nights, "nights", "y"),
            (wiki, "views", "wiki"),
            (gdelt, "gshare", "gshare"),
            (gdelt, "tone", "tone"),
        ):
            rows = source[source["geo"] == geo]
            series = pd.Series(
                rows[column].to_numpy(dtype=float),
                index=pd.PeriodIndex(rows["month"], freq="M"),
            )
            frame[name] = series.reindex(index)
        panel[geo] = frame
    return panel


def growth(frame: pd.DataFrame, column: str) -> pd.Series:
    values = frame[column]
    if column == "tone":
        return values - values.shift(12)
    with np.errstate(divide="ignore", invalid="ignore"):
        logged = np.log(values.where(values > 0))
    return logged - logged.shift(12)


def feature_table(frame: pd.DataFrame, h: int) -> pd.DataFrame:
    """One row per target month t, features built from origin o = t - h."""
    d_y = growth(frame, "y")
    dbar_y = d_y.rolling(3).mean()
    table = pd.DataFrame(index=frame.index)
    table["target"] = d_y
    table["dbar_y"] = dbar_y.shift(h)
    for column, name in (("wiki", "dwiki"), ("gshare", "dgdelt"), ("tone", "dtone")):
        d_s = growth(frame, column)
        table[name] = d_s - d_s.rolling(3).mean().shift(h)

    def contaminated(t: pd.Period) -> bool:
        months = [t, *(t - h - k for k in range(3))]
        return any(in_covid(m) or in_covid(m - 12) for m in months)

    table["covid"] = [contaminated(t) for t in table.index]
    return table


@dataclass(frozen=True)
class Forecast:
    point: float
    low: float
    high: float


def ols(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    design = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ beta
    return beta, residuals


def regression_forecast(
    train: pd.DataFrame, row: pd.Series, regressors: tuple[str, ...], base: float
) -> Forecast | None:
    columns = list(regressors)
    train = train.dropna(subset=["target", *columns])
    if len(train) < len(columns) + 8 or row[columns].isna().any():
        return None
    beta, residuals = ols(train[columns].to_numpy(), train["target"].to_numpy())
    predicted = beta[0] + float(np.dot(beta[1:], row[columns].to_numpy(dtype=float)))
    low_q, high_q = np.quantile(residuals, INTERVAL_Q)
    return Forecast(
        point=base * math.exp(predicted),
        low=base * math.exp(predicted + low_q),
        high=base * math.exp(predicted + high_q),
    )


def airline_forecasts(args: tuple[str, pd.Series, list[pd.Period]]) -> dict:
    """SARIMA(0,1,1)(0,1,1)12 on log y per origin; returns {(o, h): Forecast}."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    geo, y, origins = args
    logged = np.log(y.where(y > 0))
    logged[[in_covid(m) for m in logged.index]] = np.nan
    out = {}
    for origin in origins:
        history = logged[logged.index <= origin]
        if history.iloc[-1:].isna().any():
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = SARIMAX(
                history.to_timestamp(),
                order=(0, 1, 1),
                seasonal_order=(0, 1, 1, 12),
            ).fit(disp=False)
            prediction = model.get_forecast(len(HORIZONS))
            mean = prediction.predicted_mean.to_numpy()
            interval = prediction.conf_int(alpha=0.2).to_numpy()
        for i, h in enumerate(HORIZONS):
            out[(origin, h)] = Forecast(
                point=math.exp(mean[i]),
                low=math.exp(interval[i, 0]),
                high=math.exp(interval[i, 1]),
            )
    return geo, out


def run(period: str, gdelt_file: str = "gdelt.csv") -> pd.DataFrame:
    panel = load_panel(gdelt_file)
    start, end = PERIODS[period]
    targets = pd.period_range(start, end, freq="M")
    origins = sorted({t - h for t in targets for h in HORIZONS})

    features = {(geo, h): feature_table(frame, h) for geo, frame in panel.items() for h in HORIZONS}

    with ProcessPoolExecutor() as pool:
        airline = dict(
            pool.map(
                airline_forecasts,
                [(geo, frame["y"], origins) for geo, frame in panel.items()],
            )
        )

    records = []
    for h in HORIZONS:
        pooled = pd.concat([features[(geo, h)].assign(geo=geo) for geo in panel], axis=0)
        pooled = pooled[~pooled["covid"]]
        for t in targets:
            origin = t - h
            pool_train = pooled[pooled.index <= origin]
            for geo, frame in panel.items():
                actual = frame["y"].get(t)
                base = frame["y"].get(t - 12)
                if pd.isna(actual) or pd.isna(base) or pd.isna(frame["y"].get(origin)):
                    continue
                table = features[(geo, h)]
                row = table.loc[t]
                train = table[(table.index <= origin) & ~table["covid"]]

                forecasts: dict[str, Forecast | None] = {
                    "SN": Forecast(base, math.nan, math.nan),
                    "AIRLINE": airline[geo].get((origin, h)),
                }
                dbar = row["dbar_y"]
                forecasts["SNG"] = (
                    None if pd.isna(dbar) else Forecast(base * math.exp(dbar), math.nan, math.nan)
                )
                for model, regressors in REGRESSORS.items():
                    source = pool_train if model.startswith("POOL") else train
                    forecasts[model] = regression_forecast(source, row, regressors, base)

                for model, forecast in forecasts.items():
                    if forecast is None:
                        continue
                    records.append(
                        {
                            "geo": geo,
                            "target": str(t),
                            "h": h,
                            "model": model,
                            "actual": actual,
                            "forecast": forecast.point,
                            "low": forecast.low,
                            "high": forecast.high,
                        }
                    )

    errors = pd.DataFrame(records)
    scales = {
        geo: frame["y"]
        .diff(12)
        .abs()[(frame.index >= SCALE_WINDOW[0]) & (frame.index <= SCALE_WINDOW[1])]
        .mean()
        for geo, frame in panel.items()
    }
    errors["scaled_abs_error"] = (errors["actual"] - errors["forecast"]).abs() / errors["geo"].map(
        scales
    )
    errors["covered"] = (
        (errors["actual"] >= errors["low"]) & (errors["actual"] <= errors["high"])
    ).astype(float)
    errors.loc[errors["low"].isna(), "covered"] = np.nan
    errors["ape"] = (errors["actual"] - errors["forecast"]).abs() / errors["actual"]
    return errors


def common_sample(errors: pd.DataFrame, models: tuple[str, ...]) -> pd.DataFrame:
    """Keep only (geo, target, h) cells every listed model forecast, so
    MASE comparisons are like for like."""
    subset = errors[errors["model"].isin(models)]
    counts = subset.groupby(["geo", "target", "h"])["model"].nunique()
    complete = counts[counts == len(models)].index
    return subset.set_index(["geo", "target", "h"]).loc[complete].reset_index()


def dm_test(loss_a: np.ndarray, loss_b: np.ndarray, h: int = 3) -> float:
    """Two-sided Diebold-Mariano p-value with the HLN small-sample fix.
    Negative mean difference means model a is better."""
    diff = loss_a - loss_b
    n = len(diff)
    if n < 6 or np.allclose(diff, 0):
        return math.nan
    centred = diff - diff.mean()
    gamma = [centred @ centred / n] + [centred[k:] @ centred[:-k] / n for k in range(1, h)]
    variance = gamma[0] + 2 * sum(gamma[1:])
    if variance <= 0:
        variance = gamma[0]
    statistic = diff.mean() / math.sqrt(variance / n)
    statistic *= math.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return float(2 * stats.t.sf(abs(statistic), df=n - 1))


def summarise(errors: pd.DataFrame, models: tuple[str, ...]) -> pd.DataFrame:
    sample = common_sample(errors, models)
    table = sample.pivot_table(
        index="geo", columns="model", values="scaled_abs_error", aggfunc="mean"
    )[list(models)]
    return table


def write_report(
    period: str,
    errors: pd.DataFrame,
    primary: str | None,
    baseline: str | None,
    label: str = "",
) -> str:
    RESULTS_DIR.mkdir(exist_ok=True)
    name = f"{period}{label}"
    errors.to_csv(RESULTS_DIR / f"{name}_errors.csv", index=False)

    suffix = " (phase 2: pre-COVID GDELT)" if label else ""
    lines = [f"# Nowcast backtest: {period}{suffix}", ""]
    start, end = PERIODS[period]
    lines.append(f"Target months {start} .. {end}, horizons {HORIZONS}.")
    lines.append("")

    # 1. All models on the common sample (country x target x h that every
    # model could forecast - GDELT models need 2018+ history).
    mase = summarise(errors, MODELS)
    relative = mase.div(mase["SN"], axis=0)
    mase.to_csv(RESULTS_DIR / f"{name}_mase.csv")
    lines += [
        "## MASE by model (common sample, all countries)",
        "",
        "| model | median MASE | median rel. to SN | countries ≤ 0.90×SN | "
        "mean APE | 80% coverage |",
        "|---|---|---|---|---|---|",
    ]
    sample = common_sample(errors, MODELS)
    for model in MODELS:
        model_rows = sample[sample["model"] == model]
        coverage = model_rows["covered"].dropna()
        coverage_text = f"{coverage.mean():.0%}" if len(coverage) else "n/a"
        lines.append(
            f"| {model} | {mase[model].median():.3f} | {relative[model].median():.3f} | "
            f"{int((relative[model] <= 0.90).sum())}/{len(relative)} | "
            f"{model_rows['ape'].mean():.1%} | {coverage_text} |"
        )
    lines.append("")

    # 2. Relative MASE by horizon.
    by_h = sample.groupby(["h", "model", "geo"])["scaled_abs_error"].mean().unstack("model")
    lines += [
        "## Median relative MASE vs SN, by horizon",
        "",
        "| h | " + " | ".join(MODELS) + " |",
        "|---|" + "---|" * len(MODELS),
    ]
    for h in HORIZONS:
        rel_h = by_h.loc[h].div(by_h.loc[h]["SN"], axis=0).median()
        lines.append(f"| {h} | " + " | ".join(f"{rel_h[m]:.3f}" for m in MODELS) + " |")
    lines.append("")

    if period == "dev":
        alt_median = relative[list(ALT_MODELS)].median()
        base_median = relative[list(BASELINES[1:])].median()
        lines += [
            "## Selection (pre-registered rule)",
            "",
            f"- Primary alt-data model: **{alt_median.idxmin()}** "
            f"(median rel. MASE {alt_median.min():.3f})",
            f"- Best official-data-only baseline: **{base_median.idxmin()}** "
            f"(median rel. MASE {base_median.min():.3f})",
            "",
        ]

    if primary and baseline:
        pair = common_sample(errors, ("SN", baseline, primary))
        per_target = (
            pair.groupby(["geo", "model", "target"])["scaled_abs_error"].mean().unstack("model")
        )
        rows = []
        for geo, block in per_target.groupby(level="geo"):
            block = block.sort_index()
            sn, base, prim = (block[m].to_numpy() for m in ("SN", baseline, primary))
            rows.append(
                {
                    "geo": geo,
                    "rel_sn": prim.mean() / sn.mean(),
                    "rel_base": prim.mean() / base.mean(),
                    "p_vs_sn": dm_test(prim, sn),
                    "p_vs_base": dm_test(prim, base),
                }
            )
        verdict = pd.DataFrame(rows).set_index("geo")
        verdict.to_csv(RESULTS_DIR / f"{name}_verdict.csv")
        n = len(verdict)
        beat_sn = int((verdict["rel_sn"] <= 0.90).sum())
        beat_base = int((verdict["rel_base"] < 1.0).sum())
        significant_sn = int(((verdict["p_vs_sn"] < 0.1) & (verdict["rel_sn"] < 1)).sum())
        significant_base = int(((verdict["p_vs_base"] < 0.1) & (verdict["rel_base"] < 1)).sum())
        lines += [
            f"## Gate: {primary} vs SN and vs {baseline}",
            "",
            f"- Countries with rel. MASE vs SN ≤ 0.90: **{beat_sn}/{n}** "
            f"(pass needs ≥ {n // 2 + 1}) → **{'PASS' if beat_sn > n / 2 else 'FAIL'}**",
            f"- Countries beating {baseline}: **{beat_base}/{n}** "
            f"→ stricter check **{'PASS' if beat_base > n / 2 else 'FAIL'}**",
            f"- DM p < 0.10 better than SN: {significant_sn}; "
            f"better than {baseline}: {significant_base}",
            "",
            "| geo | rel. vs SN | rel. vs "
            + baseline
            + " | DM p vs SN | DM p vs "
            + baseline
            + " |",
            "|---|---|---|---|---|",
        ]
        for geo, row in verdict.iterrows():
            lines.append(
                f"| {geo} | {row['rel_sn']:.3f} | {row['rel_base']:.3f} | "
                f"{row['p_vs_sn']:.3f} | {row['p_vs_base']:.3f} |"
            )
        lines.append("")

    lines += [
        "## Per-country MASE (common sample)",
        "",
        "| geo | " + " | ".join(MODELS) + " |",
        "|---|" + "---|" * len(MODELS),
    ]
    for geo, row in mase.iterrows():
        lines.append(f"| {geo} | " + " | ".join(f"{row[m]:.3f}" for m in MODELS) + " |")

    report = "\n".join(lines) + "\n"
    (RESULTS_DIR / f"{name}.md").write_text(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=sorted(PERIODS), required=True)
    parser.add_argument("--primary", choices=ALT_MODELS)
    parser.add_argument("--baseline", choices=BASELINES[1:])
    parser.add_argument(
        "--phase",
        choices=("1", "2"),
        default="1",
        help="2 = pre-COVID GDELT robustness check (data/gdelt_full.csv)",
    )
    args = parser.parse_args()

    if args.period == "holdout" and not (args.primary and args.baseline):
        parser.error("holdout requires --primary and --baseline chosen on dev")

    gdelt_file, label = ("gdelt_full.csv", "_phase2") if args.phase == "2" else ("gdelt.csv", "")
    errors = run(args.period, gdelt_file)
    print(write_report(args.period, errors, args.primary, args.baseline, label))


if __name__ == "__main__":
    main()
