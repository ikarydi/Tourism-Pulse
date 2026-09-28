"""Load monthly flights per airport from EUROCONTROL.

    python -m tourism_pulse_api.ingestion.eurocontrol
    python -m tourism_pulse_api.ingestion.eurocontrol --full
    python -m tourism_pulse_api.ingestion.eurocontrol --dry-run

Writes, per month, for EU27 countries, curated destinations (airports
within 50 km), and the NUTS 2 and NUTS 3 regions containing an airport:

- flight_arrivals: IFR arrivals at the place's airports (with a per-airport
  breakdown for countries and destinations),
- flight_arrivals_growth: change against the same month a year earlier,
  over the airports that report in both months.

The first run (or --full) writes every month from 2016; later runs rewrite
the last 13 months. Yearly files are cached in --cache-dir; the current
and previous year are downloaded again on every run.
"""

import argparse
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

from tourism_pulse_api.db.models import Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurocontrol.parser import (
    AIRPORTS_URL,
    FIRST_YEAR,
    FLIGHTS_URL,
    airport_coordinates,
    monthly_airports,
)
from tourism_pulse_api.ingestion.eurocontrol.service import (
    ARRIVALS,
    SOURCE_NAME,
    map_airports,
    upsert_flights,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.ingestion.wikipedia_monthly.articles import USER_AGENT

DEFAULT_CACHE_DIR = Path("data/eurocontrol_cache")
REFRESH_MONTHS = 13


def _get(url: str, path: Path, *, refresh: bool) -> str:
    if refresh or not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
            body = response.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(body)
        temporary.replace(path)
    return path.read_text(encoding="utf-8-sig")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.eurocontrol")
    parser.add_argument("--full", action="store_true", help="rewrite every month from 2016")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args(argv)

    this_year = date.today().year
    texts: list[str] = []
    fresh: list[str] = []
    try:
        for year in range(FIRST_YEAR, this_year + 1):
            path = args.cache_dir / f"airport_traffic_{year}.csv"
            refresh = year >= this_year - 1
            try:
                body = _get(FLIGHTS_URL.format(year=year), path, refresh=refresh)
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and year == this_year:
                    continue  # the new year's file appears with January's data
                raise
            texts.append(body)
            if refresh:
                fresh.append(body)
        airports_csv = _get(AIRPORTS_URL, args.cache_dir / "ourairports.csv", refresh=False)
    except OSError as exc:
        print(f"[FAILED] download: {exc}", file=sys.stderr)
        return 1

    monthly = monthly_airports(texts)
    if monthly.empty:
        print("[FAILED] no airport rows parsed", file=sys.stderr)
        return 1
    latest = monthly["month"].max()
    coordinates = airport_coordinates(airports_csv, set(monthly["icao"]))
    print(
        f"{monthly['icao'].nunique()} airports, {monthly['month'].min()}..{latest}, "
        f"{len(coordinates)} with coordinates",
        flush=True,
    )

    db = SessionLocal()
    try:
        mapping = map_airports(db, monthly, coordinates)
        first_load = (
            db.query(Signal.id)
            .filter(Signal.signal_type == ARRIVALS, Signal.source == SOURCE_NAME)
            .first()
            is None
        )
        since = (
            pd.Period(f"{FIRST_YEAR}-01", "M")
            if args.full or first_load
            else latest - (REFRESH_MONTHS - 1)
        )
        if args.dry_run:
            print(f"[DRY RUN] {len(mapping.airports)} places, months from {since}")
            return 0
        recent = monthly_airports(fresh)
        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset="airport_traffic_monthly",
            raw_payload=recent.astype({"month": str}).to_csv(index=False),
            content_type="text/csv",
            source_url=FLIGHTS_URL.format(year=this_year),
        )
        written = upsert_flights(
            db, monthly, mapping, since=since, source_observation_id=observation.id
        )
        print(
            f"[INGESTED] {written.signals} monthly values and {written.breakdowns} airport "
            f"values for {written.places} places, months {since}..{latest}"
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
