"""Issue forecasts from the latest data, or rebuild the backtest.

python -m tourism_pulse_api.forecasting
python -m tourism_pulse_api.forecasting --backtest 2024-06 2026-05
"""

import argparse

import pandas as pd

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.forecasting.service import run_backtest, run_live


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.forecasting")
    parser.add_argument(
        "--backtest",
        nargs=2,
        metavar=("FIRST_ORIGIN", "LAST_ORIGIN"),
        help="recompute backtest forecasts for origins in this range (YYYY-MM)",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        if args.backtest:
            first, last = (pd.Period(value, "M") for value in args.backtest)
            written = run_backtest(db, first, last)
            print(f"[BACKTEST] {written} forecasts for origins {first}..{last}")
        else:
            written = run_live(db)
            print(f"[ISSUED] {written} forecasts (existing live forecasts are kept)")
        db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
