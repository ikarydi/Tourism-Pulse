"""Gate 3 backtest: flights and the hotel survey at horizons 1-3.

See PREREGISTRATION.md. Run from the repo root, development first:

    python -m research.gate3.backtest --period dev

then, once results/SELECTION.md is committed, exactly once:

    python -m research.gate3.backtest --period holdout --best-t WG_FS

Everything in Gate 2's set-up is reused (research.forecast.backtest):
features, COVID exclusion, pooled direct regressions with residual-quantile
intervals, and MASE scaling. Results go to research/gate3/results/.
"""

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from research.forecast.backtest import (
    HORIZONS,
    PERIODS,
    SCALE_WINDOW,
    regression,
    table_lines,
)
from research.forecast.backtest import feature_table as gate2_features
from research.nowcast.backtest import Forecast, common_sample, in_covid, load_panel

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"

DECISION_HORIZONS = (1, 2, 3)
LATER_HORIZONS = tuple(h for h in HORIZONS if h not in DECISION_HORIZONS)
ELIGIBLE_SHARE = 0.75
MEDIAN_BAR = 0.97

BASE = ("gbar", "wiki", "gdelt", "tone")
REGRESSORS: dict[str, tuple[str, ...]] = {
    "WG": BASE,
    "WG_F": (*BASE, "fl"),
    "WG_S": (*BASE, "sv"),
    "WG_FS": (*BASE, "fl", "sv"),
    # Descriptive only.
    "WG_S2": (*BASE, "sv2"),
    "GR_F": ("gbar", "fl"),
}
CANDIDATES = ("WG_F", "WG_S", "WG_FS")
DESCRIPTIVE = ("WG_S2", "GR_F")
MODELS = ("SN", *REGRESSORS)
# Which gate each new source belongs to.
SOURCE_MODEL = {"flights": "WG_F", "survey": "WG_S"}
SOURCES_OF = {"WG_F": {"flights"}, "WG_S": {"survey"}, "WG_FS": {"flights", "survey"}}


# --- data -------------------------------------------------------------------------------


def flight_growth() -> dict[str, pd.Series]:
    """geo -> month -> log(sum arrivals / sum arrivals a year earlier) over
    the airports reporting arrivals in both months."""
    flights = pd.read_csv(DATA_DIR / "flights.csv")
    flights = flights[flights["arrivals"] > 0].copy()
    flights["month"] = pd.PeriodIndex(flights["month"], freq="M")
    out: dict[str, pd.Series] = {}
    for geo, block in flights.groupby("geo"):
        arrivals = {
            (icao, month): float(value)
            for icao, month, value in zip(
                block["icao"], block["month"], block["arrivals"], strict=True
            )
        }
        values: dict[pd.Period, float] = {}
        for month, rows in block.groupby("month"):
            now_total = before_total = 0.0
            for icao in rows["icao"]:
                before = arrivals.get((icao, month - 12))
                if before is None:
                    continue
                now_total += arrivals[(icao, month)]
                before_total += before
            if now_total > 0 and before_total > 0:
                values[month] = math.log(now_total / before_total)
        out[str(geo)] = pd.Series(values, dtype=float)
    return out


def survey_change() -> dict[str, pd.Series]:
    """geo -> month -> (expected-demand balance minus the same month a year
    earlier) / 100."""
    survey = pd.read_csv(DATA_DIR / "hotel_survey.csv")
    survey["month"] = pd.PeriodIndex(survey["month"], freq="M")
    out: dict[str, pd.Series] = {}
    for geo, block in survey.groupby("geo"):
        balance = block.set_index("month")["demand_expected"].astype(float)
        full = balance.reindex(pd.period_range(balance.index.min(), balance.index.max(), freq="M"))
        out[str(geo)] = (full - full.shift(12)) / 100
    return out


def gate3_panel() -> dict[str, pd.DataFrame]:
    panel = load_panel("gdelt_full.csv")
    flights, survey = flight_growth(), survey_change()
    for geo, frame in panel.items():
        frame["fl"] = flights.get(geo, pd.Series(dtype=float)).reindex(frame.index)
        frame["sv"] = survey.get(geo, pd.Series(dtype=float)).reindex(frame.index)
    return panel


def feature_table(frame: pd.DataFrame, h: int) -> pd.DataFrame:
    """Gate 2's features plus fl and sv at a = o + 1, and sv2 at o + 2.

    Gate 2's COVID flag already covers a and a - 12. sv2's month o + 2 and
    its year-earlier month get their own flag, used only for WG_S2."""
    table = gate2_features(frame, h)
    table["fl"] = frame["fl"].shift(h - 1)
    table["sv"] = frame["sv"].shift(h - 1)
    table["sv2"] = frame["sv"].shift(h - 2)
    table["covid_s2"] = table["covid"] | [
        in_covid(t - h + 2) or in_covid(t - h + 2 - 12) for t in table.index
    ]
    return table


def _covid_column(model: str) -> str:
    return "covid_s2" if model == "WG_S2" else "covid"


# --- backtest ---------------------------------------------------------------------------


def run(period: str, panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    start, end = PERIODS[period]
    targets = pd.period_range(start, end, freq="M")
    features = {(geo, h): feature_table(frame, h) for geo, frame in panel.items() for h in HORIZONS}
    records = []
    for h in HORIZONS:
        pooled = pd.concat([features[(geo, h)].assign(geo=geo) for geo in panel], axis=0)
        for t in targets:
            origin = t - h
            known = pooled[pooled.index <= origin]
            trains = {model: known[~known[_covid_column(model)]] for model in REGRESSORS}
            for geo, frame in panel.items():
                actual, base = frame["y"].get(t), frame["y"].get(t - 12)
                if pd.isna(actual) or pd.isna(base) or pd.isna(frame["y"].get(origin)):
                    continue
                row = features[(geo, h)].loc[t]
                forecasts: dict[str, Forecast | None] = {"SN": Forecast(base, math.nan, math.nan)}
                for model, columns in REGRESSORS.items():
                    forecasts[model] = (
                        None
                        if row[_covid_column(model)]
                        else regression(trains[model], row, columns, base)
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
    return errors


# --- scoring ----------------------------------------------------------------------------


def at(errors: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    return errors[errors["h"].isin(horizons)]


def eligible(errors: pd.DataFrame, model: str, reference: str) -> list[str]:
    """Countries where both models forecast >= 75% of the country's scored
    cells (the cells seasonal naive covers)."""
    cells = errors[errors["model"] == "SN"].groupby("geo").size()
    both = common_sample(errors, (model, reference))
    shared = both[both["model"] == model].groupby("geo").size()
    return sorted(
        geo for geo, total in cells.items() if shared.get(geo, 0) >= ELIGIBLE_SHARE * total
    )


def pair_ratios(errors: pd.DataFrame, model: str, reference: str) -> pd.Series:
    """Per eligible country: MASE of model over MASE of reference, on the
    cells both forecast."""
    geos = eligible(errors, model, reference)
    both = common_sample(errors[errors["geo"].isin(geos)], (model, reference))
    mase = both.pivot_table(index="geo", columns="model", values="scaled_abs_error", aggfunc="mean")
    return (mase[model] / mase[reference]).sort_index()


def sign_test(wins: int, n: int) -> float:
    return float(stats.binomtest(wins, n, 0.5).pvalue) if n else math.nan


def gate(ratios: pd.Series) -> tuple[int, int, float, bool]:
    n = len(ratios)
    wins = int((ratios < 1).sum())
    median = float(ratios.median()) if n else math.nan
    return wins, n, median, n > 0 and wins >= n // 2 + 1 and median <= MEDIAN_BAR


def coverage(errors: pd.DataFrame, model: str, geos: list[str]) -> float:
    rows = errors[(errors["model"] == model) & errors["geo"].isin(geos)]
    return float(rows["covered"].dropna().mean())


def comparison_lines(errors: pd.DataFrame, horizons: tuple[int, ...], title: str) -> list[str]:
    lines = [f"## {title}", ""]
    sample = at(errors, horizons)
    rows = []
    for model in (*CANDIDATES, *DESCRIPTIVE):
        ratios = pair_ratios(sample, model, "WG")
        wins, n, median, _ = gate(ratios)
        both = common_sample(sample[sample["geo"].isin(ratios.index)], (model, "WG"))
        ape = both.groupby("model")["ape"].mean()
        rows.append(
            [
                model,
                f"{wins}/{n}",
                f"{median:.3f}" if n else "n/a",
                f"{sign_test(wins, n):.3f}" if n else "n/a",
                f"{ape.get(model, math.nan):.2%}",
                f"{ape.get('WG', math.nan):.2%}",
                f"{coverage(sample, model, list(ratios.index)):.0%}",
            ]
        )
    lines += table_lines(
        [
            "model vs WG",
            "countries better",
            "median MASE ratio",
            "sign test p",
            "model MAPE",
            "WG MAPE",
            "model 80% coverage",
        ],
        rows,
    )
    return lines


def horizon_lines(errors: pd.DataFrame) -> list[str]:
    """MAPE by horizon: SN and WG on WG's cells, then each model's MAPE
    relative to WG's on the cells the two share (so country sets match)."""
    lines = ["Mean absolute percentage error by horizon, SN and WG on WG's cells:", ""]
    base_rows, relative_rows = [], []
    for h in HORIZONS:
        sample = errors[errors["h"] == h]
        pair = common_sample(sample, ("SN", "WG"))
        mape = pair.groupby("model")["ape"].mean()
        base_rows.append([str(h), f"{mape['SN']:.2%}", f"{mape['WG']:.2%}"])
        cells = [str(h)]
        for model in (*CANDIDATES, *DESCRIPTIVE):
            both = common_sample(sample, (model, "WG")).groupby("model")["ape"].mean()
            cells.append(f"{both[model] / both['WG'] - 1:+.1%}")
        relative_rows.append(cells)
    lines += table_lines(["h", "SN", "WG"], base_rows)
    lines += [
        "Each model's MAPE relative to WG's on the cells both forecast (negative = more accurate):",
        "",
    ]
    lines += table_lines(["h", *CANDIDATES, *DESCRIPTIVE], relative_rows)
    return lines


def per_country_lines(errors: pd.DataFrame) -> list[str]:
    sample = at(errors, DECISION_HORIZONS)
    ratios = {model: pair_ratios(sample, model, "WG") for model in CANDIDATES}
    geos = sorted(set().union(*(r.index for r in ratios.values())))
    rows = [
        [geo, *(f"{ratios[m][geo]:.3f}" if geo in ratios[m].index else "n/a" for m in CANDIDATES)]
        for geo in geos
    ]
    return [
        "## Per country, h ≤ 3 (MASE ratio to WG)",
        "",
        *table_lines(["geo", *CANDIDATES], rows),
    ]


# --- reports ----------------------------------------------------------------------------


def select(errors: pd.DataFrame) -> tuple[str, pd.Series]:
    sample = common_sample(at(errors, DECISION_HORIZONS), CANDIDATES)
    mase = sample.pivot_table(
        index="geo", columns="model", values="scaled_abs_error", aggfunc="mean"
    )
    means = mase[list(CANDIDATES)].mean()
    return str(means.idxmin()), means


def dev_report(errors: pd.DataFrame) -> str:
    start, end = PERIODS["dev"]
    lines = [
        "# Gate 3 backtest: development",
        "",
        f"Target months {start} .. {end}, horizons 1-12; decisions use h ≤ 3.",
        "",
    ]
    lines += comparison_lines(errors, DECISION_HORIZONS, "h ≤ 3, each model against WG")
    lines += comparison_lines(errors, LATER_HORIZONS, "h = 4-12 (descriptive)")
    lines += horizon_lines(errors)
    best, means = select(errors)
    lines += [
        "## Selection (pre-registered: lowest mean MASE at h ≤ 3 across countries, "
        "on the three candidates' common sample)",
        "",
        ", ".join(f"{model} {means[model]:.3f}" for model in CANDIDATES),
        "",
        f"- BEST_T: **{best}**",
        "",
    ]
    lines += per_country_lines(errors)
    return "\n".join(lines)


def shipped_model(best_t: str, passed: dict[str, bool]) -> str:
    """Pre-registered: BEST_T if every source it uses passed; else the
    single-source model whose gate passed; else WG."""
    if all(passed[source] for source in SOURCES_OF[best_t]):
        return best_t
    singles = [SOURCE_MODEL[source] for source, ok in passed.items() if ok]
    if len(singles) == 1:
        return singles[0]
    return "WG"


def holdout_report(errors: pd.DataFrame, best_t: str) -> str:
    start, end = PERIODS["holdout"]
    decision = at(errors, DECISION_HORIZONS)
    results = {}
    for source, model in SOURCE_MODEL.items():
        ratios = pair_ratios(decision, model, "WG")
        results[source] = (model, ratios, *gate(ratios))
    passed = {source: result[5] for source, result in results.items()}
    shipped = shipped_model(best_t, passed)
    shipped_geos = (
        list(pair_ratios(decision, shipped, "WG").index)
        if shipped != "WG"
        else sorted(decision[decision["model"] == "WG"]["geo"].unique())
    )
    shipped_coverage = coverage(decision, shipped, shipped_geos)
    calibrated = 0.70 <= shipped_coverage <= 0.90

    def verdict(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    lines = [
        "# Gate 3 backtest: holdout",
        "",
        f"Target months {start} .. {end}, horizons 1-12; decisions use h ≤ 3. "
        f"Selected on development: BEST_T = {best_t}.",
        "",
        "## Gate",
        "",
    ]
    for label, source in (("G3-A flights", "flights"), ("G3-B survey", "survey")):
        model, ratios, wins, n, median, ok = results[source]
        lines.append(
            f"- **{label}**: {model} beats WG in **{wins}/{n}** eligible countries, median MASE "
            f"ratio **{median:.3f}** (needs ≥ {n // 2 + 1} and ≤ {MEDIAN_BAR}), sign test "
            f"p = {sign_test(wins, n):.3f} → **{verdict(ok)}**"
        )
    lines += [
        f"- Shipped model at h ≤ 3 (rule: BEST_T if all its sources passed, else the single "
        f"passing source, else WG): **{shipped}**",
        f"- **G3-C calibration**: {shipped} 80% intervals cover **{shipped_coverage:.0%}** of "
        f"eligible holdout outcomes at h ≤ 3 (needs 70-90%)"
        + (f" → **{verdict(calibrated)}**" if shipped != "WG" else " (WG stays; for reference)"),
        "",
    ]
    lines += comparison_lines(errors, DECISION_HORIZONS, "h ≤ 3, each model against WG")
    lines += comparison_lines(errors, LATER_HORIZONS, "h = 4-12 (descriptive)")
    lines += horizon_lines(errors)
    lines += per_country_lines(errors)
    frame = pd.DataFrame(
        {results[s][0]: results[s][1] for s in SOURCE_MODEL} | {"shipped": shipped}
    )
    frame.to_csv(RESULTS_DIR / "holdout_verdict.csv")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=tuple(PERIODS), required=True)
    parser.add_argument("--best-t", choices=CANDIDATES)
    args = parser.parse_args()
    if args.period == "holdout" and not args.best_t:
        parser.error("the holdout needs --best-t from results/SELECTION.md")

    RESULTS_DIR.mkdir(exist_ok=True)
    errors = run(args.period, gate3_panel())
    errors.to_csv(RESULTS_DIR / f"{args.period}_errors.csv", index=False)
    report = dev_report(errors) if args.period == "dev" else holdout_report(errors, args.best_t)
    (RESULTS_DIR / f"{args.period}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
