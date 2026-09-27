"""Rolling-origin forecast backtest for Gate 2. See PREREGISTRATION.md.

Run from the repo root, development first:

    python -m research.forecast.backtest --period dev

then, once SELECTION.md is committed, exactly once:

    python -m research.forecast.backtest --period holdout \\
        --best-off AIRLINE --best-alt POOL_GR_W

Results go to research/forecast/results/.
"""

import os

# One BLAS/torch thread per process: the SARIMA fits run in a process pool.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import math  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from research.nowcast.backtest import (  # noqa: E402
    Forecast,
    airline_forecasts,
    common_sample,
    dm_test,
    growth,
    in_covid,
    load_panel,
    ols,
)

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"

HORIZONS = tuple(range(1, 13))
PERIODS = {
    "dev": (pd.Period("2023-07", "M"), pd.Period("2025-06", "M")),
    "holdout": (pd.Period("2025-07", "M"), pd.Period("2026-06", "M")),
}
SCALE_WINDOW = (pd.Period("2016-01", "M"), pd.Period("2019-12", "M"))
N_UNITS = 30
INTERVAL_Q = (0.10, 0.90)
# Attention is known one month past the last official month.
ATTENTION_LEAD = 1

OFFICIAL = ("SNG", "AIRLINE", "POOL_GR", "CHRONOS", "COMBO")
ALTERNATIVE = ("POOL_GR_W", "POOL_GR_WG")
MODELS = ("SN", *OFFICIAL, *ALTERNATIVE)
REGRESSORS = {
    "POOL_GR": ("gbar",),
    "POOL_GR_W": ("gbar", "wiki"),
    "POOL_GR_WG": ("gbar", "wiki", "gdelt", "tone"),
}
COMBO_MEMBERS = ("AIRLINE", "POOL_GR", "CHRONOS")


def feature_table(frame: pd.DataFrame, h: int) -> pd.DataFrame:
    """One row per target month t: the year-on-year log growth to predict
    and the features known at origin o = t - h (attention at a = o + 1)."""
    g_y = growth(frame, "y")
    table = pd.DataFrame(index=frame.index)
    table["target"] = g_y
    table["gbar"] = g_y.rolling(3).mean().shift(h)
    attention_shift = h - ATTENTION_LEAD
    for column, name in (("wiki", "wiki"), ("gshare", "gdelt"), ("tone", "tone")):
        table[name] = growth(frame, column).rolling(3).mean().shift(attention_shift)

    def contaminated(t: pd.Period) -> bool:
        origin, attention = t - h, t - attention_shift
        months = [t, *(origin - k for k in range(3)), *(attention - k for k in range(3))]
        return any(in_covid(m) or in_covid(m - 12) for m in months)

    table["covid"] = [contaminated(t) for t in table.index]
    return table


def regression(train: pd.DataFrame, row: pd.Series, columns: tuple[str, ...], base: float):
    train = train.dropna(subset=["target", *columns])
    if len(train) < len(columns) + 8 or row[list(columns)].isna().any():
        return None
    beta, residuals = ols(train[list(columns)].to_numpy(), train["target"].to_numpy())
    predicted = beta[0] + float(np.dot(beta[1:], row[list(columns)].to_numpy(dtype=float)))
    low_q, high_q = np.quantile(residuals, INTERVAL_Q)
    return Forecast(
        point=base * math.exp(predicted),
        low=base * math.exp(predicted + low_q),
        high=base * math.exp(predicted + high_q),
    )


def chronos_forecasts(panel: dict[str, pd.DataFrame], origins: list[pd.Period]) -> dict:
    """{(geo, origin, h): Forecast} from Chronos-Bolt small, zero-shot."""
    import torch
    from chronos import BaseChronosPipeline

    torch.set_num_threads(4)
    pipeline = BaseChronosPipeline.from_pretrained(
        "amazon/chronos-bolt-small", device_map="cpu", dtype=torch.float32
    )
    out = {}
    for origin in origins:
        geos, contexts = [], []
        for geo, frame in panel.items():
            y = frame["y"][frame.index <= origin]
            if pd.isna(y.iloc[-1]):
                continue
            logged = np.log(y.where(y > 0)).to_numpy(dtype=float)
            logged[[in_covid(m) for m in y.index]] = np.nan
            # Leading months before the series starts are not history.
            first = np.argmax(~np.isnan(logged))
            geos.append(geo)
            contexts.append(torch.tensor(logged[first:]))
        if not contexts:
            continue
        quantiles, _ = pipeline.predict_quantiles(
            contexts, prediction_length=len(HORIZONS), quantile_levels=[0.1, 0.5, 0.9]
        )
        values = quantiles.numpy()
        for i, geo in enumerate(geos):
            for j, h in enumerate(HORIZONS):
                low, median, high = values[i, j]
                out[(geo, origin, h)] = Forecast(
                    point=math.exp(median), low=math.exp(low), high=math.exp(high)
                )
    return out


def combine(members: list[Forecast]) -> Forecast:
    def log_mean(values: list[float]) -> float:
        return math.exp(sum(math.log(v) for v in values) / len(values))

    return Forecast(
        point=log_mean([m.point for m in members]),
        low=log_mean([m.low for m in members]),
        high=log_mean([m.high for m in members]),
    )


def run(period: str, panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    start, end = PERIODS[period]
    targets = pd.period_range(start, end, freq="M")
    origins = sorted({t - h for t in targets for h in HORIZONS})

    with ProcessPoolExecutor() as pool:
        airline = dict(
            pool.map(
                airline_forecasts,
                [(geo, frame["y"], origins, HORIZONS) for geo, frame in panel.items()],
            )
        )
    chronos = chronos_forecasts(panel, origins)

    features = {(geo, h): feature_table(frame, h) for geo, frame in panel.items() for h in HORIZONS}
    records = []
    for h in HORIZONS:
        pooled = pd.concat([features[(geo, h)].assign(geo=geo) for geo in panel], axis=0)
        pooled = pooled[~pooled["covid"]]
        for t in targets:
            origin = t - h
            train = pooled[pooled.index <= origin]
            for geo, frame in panel.items():
                actual, base = frame["y"].get(t), frame["y"].get(t - 12)
                if pd.isna(actual) or pd.isna(base) or pd.isna(frame["y"].get(origin)):
                    continue
                row = features[(geo, h)].loc[t]
                forecasts: dict[str, Forecast | None] = {
                    "SN": Forecast(base, math.nan, math.nan),
                    "AIRLINE": airline[geo].get((origin, h)),
                    "CHRONOS": chronos.get((geo, origin, h)),
                }
                forecasts["SNG"] = (
                    None
                    if row["covid"] or pd.isna(row["gbar"])
                    else Forecast(base * math.exp(row["gbar"]), math.nan, math.nan)
                )
                for model, columns in REGRESSORS.items():
                    forecasts[model] = (
                        None if row["covid"] else regression(train, row, columns, base)
                    )
                members = [forecasts[m] for m in COMBO_MEMBERS]
                forecasts["COMBO"] = (
                    combine(members) if all(m is not None for m in members) else None
                )
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
    errors["log_error"] = np.log(errors["actual"] / errors["forecast"])
    return errors


def mase_by_geo(errors: pd.DataFrame, models: tuple[str, ...]) -> pd.DataFrame:
    sample = common_sample(errors, models)
    return sample.pivot_table(
        index="geo", columns="model", values="scaled_abs_error", aggfunc="mean"
    )[list(models)]


def pair_verdict(errors: pd.DataFrame, model: str, reference: str) -> pd.DataFrame:
    """Per country: MASE ratio of model to reference on their common cells,
    and a Diebold-Mariano p-value on the per-target mean scaled errors."""
    pair = common_sample(errors, (model, reference))
    per_target = pair.groupby(["geo", "model", "target"])["scaled_abs_error"].mean().unstack("model")
    rows = []
    for geo, block in per_target.groupby(level="geo"):
        block = block.sort_index()
        a, b = block[model].to_numpy(), block[reference].to_numpy()
        rows.append({"geo": geo, "ratio": a.mean() / b.mean(), "p": dm_test(a, b, h=12)})
    return pd.DataFrame(rows).set_index("geo")


def table_lines(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(row) + " |" for row in rows),
        "",
    ]


def describe(errors: pd.DataFrame, title: str) -> list[str]:
    """Model comparison on the cells every model forecast."""
    lines = [f"## {title}", ""]
    mase = mase_by_geo(errors, MODELS)
    relative = mase.div(mase["SN"], axis=0)
    sample = common_sample(errors, MODELS)
    rows = []
    for model in MODELS:
        model_rows = sample[sample["model"] == model]
        coverage = model_rows["covered"].dropna()
        rows.append(
            [
                model,
                f"{mase[model].mean():.3f}",
                f"{relative[model].median():.3f}",
                f"{int((relative[model] <= 0.90).sum())}/{len(relative)}",
                f"{model_rows['ape'].mean():.2%}",
                f"{coverage.mean():.0%}" if len(coverage) else "n/a",
            ]
        )
    lines += table_lines(
        [
            "model",
            "mean MASE",
            "median rel. to SN",
            "countries ≤ 0.90×SN",
            "mean APE",
            "80% coverage",
        ],
        rows,
    )
    by_h = sample.groupby(["h", "model"])["ape"].mean().unstack("model")[list(MODELS)]
    lines += ["Mean absolute percentage error by horizon:", ""]
    lines += table_lines(
        ["h", *MODELS],
        [[str(h), *(f"{by_h.loc[h, m]:.2%}" for m in MODELS)] for h in HORIZONS],
    )
    n_cells = len(sample) // len(MODELS)
    lines += [f"Common sample: {n_cells} (country, target, horizon) cells.", ""]
    return lines


def dev_report(errors: pd.DataFrame) -> str:
    lines = ["# Gate 2 forecast backtest: development", ""]
    start, end = PERIODS["dev"]
    lines += [f"Target months {start} .. {end}, horizons 1-12.", ""]
    lines += describe(errors, "All models, common sample")

    official = mase_by_geo(errors, OFFICIAL).mean()
    alternative = mase_by_geo(errors, ALTERNATIVE).mean()
    lines += [
        "## Selection (pre-registered rule: lowest mean MASE across countries)",
        "",
        "Official-data candidates, on their common sample: "
        + ", ".join(f"{m} {official[m]:.3f}" for m in OFFICIAL),
        "",
        f"- BEST_OFF: **{official.idxmin()}**",
        "",
        "Attention candidates, on their common sample: "
        + ", ".join(f"{m} {alternative[m]:.3f}" for m in ALTERNATIVE),
        "",
        f"- BEST_ALT: **{alternative.idxmin()}**",
        "",
    ]
    return "\n".join(lines)


def holdout_report(errors: pd.DataFrame, best_off: str, best_alt: str) -> str:
    lines = ["# Gate 2 forecast backtest: holdout", ""]
    start, end = PERIODS["holdout"]
    lines += [
        f"Target months {start} .. {end}, horizons 1-12. "
        f"Selected on development: BEST_OFF = {best_off}, BEST_ALT = {best_alt}.",
        "",
    ]

    skill = pair_verdict(errors, best_off, "SN")
    passed_a = int((skill["ratio"] <= 0.90).sum())
    attention = pair_verdict(errors, best_alt, "POOL_GR")
    wins_b = int((attention["ratio"] < 1).sum())
    median_b = float(attention["ratio"].median())
    passed_b = wins_b >= N_UNITS // 2 + 1 and median_b <= 0.97
    head_to_head = mase_by_geo(errors, (best_alt, best_off)).mean()
    alt_ships = passed_b and head_to_head[best_alt] < head_to_head[best_off]
    shipped = best_alt if alt_ships else best_off
    coverage = errors[errors["model"] == shipped]["covered"].dropna().mean()
    passed_c = 0.70 <= coverage <= 0.90

    def verdict(passed: bool) -> str:
        return "PASS" if passed else "FAIL"

    lines += [
        "## Gate",
        "",
        f"- **G2-A skill**: {best_off} MASE ≤ 0.90 × SN in **{passed_a}/{N_UNITS}** countries "
        f"(needs ≥ {N_UNITS // 2 + 1}) → **{verdict(passed_a >= N_UNITS // 2 + 1)}**",
        f"- **G2-B attention**: {best_alt} beats POOL_GR in **{wins_b}/{N_UNITS}** countries, "
        f"median ratio **{median_b:.3f}** (needs ≥ {N_UNITS // 2 + 1} and ≤ 0.97) "
        f"→ **{verdict(passed_b)}**",
        f"- Head to head on their common sample: {best_alt} mean MASE "
        f"{head_to_head[best_alt]:.3f}, {best_off} {head_to_head[best_off]:.3f}. "
        f"Shipped model: **{shipped}**.",
        f"- **G2-C calibration**: {shipped} 80% intervals cover **{coverage:.0%}** "
        f"(needs 70-90%) → **{verdict(passed_c)}**",
        "",
    ]
    lines += describe(errors, "All models, common sample")

    chronos = pair_verdict(errors, "CHRONOS", "AIRLINE")
    lines += [
        "## Research question: CHRONOS vs AIRLINE",
        "",
        f"CHRONOS beats AIRLINE in {int((chronos['ratio'] < 1).sum())}/{len(chronos)} countries; "
        f"median ratio {chronos['ratio'].median():.3f}; DM p < 0.10 better in "
        f"{int(((chronos['p'] < 0.1) & (chronos['ratio'] < 1)).sum())}, worse in "
        f"{int(((chronos['p'] < 0.1) & (chronos['ratio'] > 1)).sum())}.",
        "",
    ]

    lines += ["## Per country", ""]
    rows = [
        [
            geo,
            f"{skill.loc[geo, 'ratio']:.3f}",
            f"{skill.loc[geo, 'p']:.3f}",
            f"{attention.loc[geo, 'ratio']:.3f}" if geo in attention.index else "n/a",
            f"{attention.loc[geo, 'p']:.3f}" if geo in attention.index else "n/a",
            f"{chronos.loc[geo, 'ratio']:.3f}" if geo in chronos.index else "n/a",
        ]
        for geo in skill.index
    ]
    lines += table_lines(
        [
            "geo",
            f"{best_off} / SN",
            "DM p",
            f"{best_alt} / POOL_GR",
            "DM p",
            "CHRONOS / AIRLINE",
        ],
        rows,
    )
    skill.join(attention, lsuffix="_skill", rsuffix="_attention").to_csv(
        RESULTS_DIR / "holdout_verdict.csv"
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=tuple(PERIODS), required=True)
    parser.add_argument("--best-off", choices=OFFICIAL)
    parser.add_argument("--best-alt", choices=ALTERNATIVE)
    args = parser.parse_args()
    if args.period == "holdout" and not (args.best_off and args.best_alt):
        parser.error("the holdout needs --best-off and --best-alt from SELECTION.md")

    RESULTS_DIR.mkdir(exist_ok=True)
    panel = load_panel("gdelt_full.csv")
    errors = run(args.period, panel)
    errors.to_csv(RESULTS_DIR / f"{args.period}_errors.csv", index=False)
    if args.period == "dev":
        report = dev_report(errors)
    else:
        report = holdout_report(errors, args.best_off, args.best_alt)
    (RESULTS_DIR / f"{args.period}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
