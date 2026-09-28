"""GDELT coverage of curated places from the daily GKG files.

    python -m tourism_pulse_api.ingestion.gdelt_gkg                  # last and this month
    python -m tourism_pulse_api.ingestion.gdelt_gkg --start 2016-01-01   # backfill

Days are fetched in parallel and each day's summary is cached under
--cache-dir, so an interrupted backfill resumes where it stopped and the
daily run only downloads new days. Whole months are always re-aggregated:
--start is moved back to the first of its month.
"""

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.gdelt_gkg.service import (
    SOURCE_NAME,
    SOURCE_URL,
    aggregate_months,
    build_targets,
    fetch_day,
    monthly_values,
    upsert,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation

DEFAULT_CACHE_DIR = Path("data/gdelt_gkg_cache")


def _first_of_previous_month(today: date) -> date:
    first = today.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.gdelt_gkg")
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    today = date.today()
    start = (args.start or _first_of_previous_month(today)).replace(day=1)
    end = args.end or today - timedelta(days=1)  # yesterday: the last complete file
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        targets = build_targets(db)
        # End the read transaction before the long download: an open one
        # holds locks that block migrations for the whole run.
        db.commit()
        print(f"{len(targets)} places, {len(days)} days ({start}..{end})", flush=True)

        results: dict[date, dict | None] = {}
        started = time.time()
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(fetch_day, day, targets, args.cache_dir) for day in days]
            for done, future in enumerate(as_completed(futures), start=1):
                day, summary = future.result()
                results[day] = summary
                if done % 100 == 0 or done == len(futures):
                    minutes = (time.time() - started) / 60
                    print(f"{done}/{len(futures)} days, {minutes:.1f} min", flush=True)

        months = aggregate_months(results)
        signals, breakdowns = monthly_values(months, [target.place_id for target in targets])
        missing = sum(summary is None for summary in results.values())
        print(
            f"{len(months)} months, {len(signals)} signal values, "
            f"{len(breakdowns)} topic values; {missing} days without a file",
            flush=True,
        )
        if args.dry_run:
            print("[DRY RUN] nothing written")
            return 0

        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset="gdelt_gkg_monthly_places",
            raw_payload=json.dumps(
                {f"{year}-{month:02d}": totals for (year, month), totals in months.items()}
            ),
            content_type="application/json",
            source_url=SOURCE_URL,
        )
        upsert(db, signals, breakdowns, source_observation_id=observation.id)
        db.commit()
        print(f"[INGESTED] {len(signals)} signal values, {len(breakdowns)} topic values")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
