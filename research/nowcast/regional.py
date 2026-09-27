"""Gate 1b: regional nowcast backtest for Hungary's 12 tourism areas.

See PREREGISTRATION_REGIONAL.md. Reuses backtest.py's engine with its
own Study settings and panel. Development first:

    python -m research.nowcast.regional --period dev

then, once the primary model and baseline are committed, exactly once:

    python -m research.nowcast.regional --period holdout --primary POOL_W --baseline POOL_GR
"""

import argparse

import numpy as np
import pandas as pd

from research.nowcast.backtest import DATA_DIR, Study, run, write_report
from research.nowcast.regional_data import ARTICLES

REGIONAL_STUDY = Study(
    title="Regional nowcast backtest (Hungary)",
    unit="areas",
    unit_singular="area",
    n_units=12,
    horizons=(1, 2),
    periods={
        "dev": (pd.Period("2023-10", "M"), pd.Period("2025-07", "M")),
        "holdout": (pd.Period("2025-08", "M"), pd.Period("2026-07", "M")),
    },
    scale_window=(pd.Period("2023-01", "M"), pd.Period("2024-12", "M")),
    baselines=("SN", "SNG", "AIRLINE", "POOL_GR"),
    alt_models=("POOL_W", "POOL_WG"),
    regressors={
        "POOL_GR": ("dbar_y",),
        "POOL_W": ("dbar_y", "dwiki"),
        "POOL_WG": ("dbar_y", "dwiki", "dgdelt"),
    },
    results_prefix="regional_",
)


def load_regional_panel() -> dict[str, pd.DataFrame]:
    nights = pd.read_csv(DATA_DIR / "ksh_areas.csv")
    views = pd.read_csv(DATA_DIR / "pageviews_regional.csv")
    gdelt = pd.read_csv(DATA_DIR / "gdelt_regional.csv")

    # A month is usable only if every listed article reports it.
    expected = {
        area: sum(len(titles) for titles in by_language.values())
        for area, by_language in ARTICLES.items()
    }
    wiki = views.groupby(["area", "month"]).agg(
        views=("views", "sum"), n_series=("series", "nunique")
    )
    wiki = wiki.reset_index()
    wiki.loc[wiki["n_series"] < wiki["area"].map(expected), "views"] = np.nan

    # +1 keeps zero-mention months defined (pre-registered).
    gdelt["gshare"] = (gdelt["articles"] + 1) / gdelt["corpus"]

    index = pd.period_range("2021-01", "2026-09", freq="M")
    panel = {}
    for area in sorted(nights["area"].unique()):
        frame = pd.DataFrame(index=index)
        for source, column, name in (
            (nights, "nights", "y"),
            (wiki, "views", "wiki"),
            (gdelt, "gshare", "gshare"),
        ):
            rows = source[source["area"] == area]
            frame[name] = pd.Series(
                rows[column].to_numpy(dtype=float),
                index=pd.PeriodIndex(rows["month"], freq="M"),
            ).reindex(index)
        panel[area] = frame
    return panel


def main() -> None:
    study = REGIONAL_STUDY
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=sorted(study.periods), required=True)
    parser.add_argument("--primary", choices=study.alt_models)
    parser.add_argument("--baseline", choices=study.baselines[1:])
    args = parser.parse_args()

    if args.period == "holdout" and not (args.primary and args.baseline):
        parser.error("holdout requires --primary and --baseline chosen on dev")

    errors = run(study, args.period, load_regional_panel())
    print(write_report(study, args.period, errors, args.primary, args.baseline))


if __name__ == "__main__":
    main()
