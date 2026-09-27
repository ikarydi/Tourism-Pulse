"""Bulk-load Eurostat tourism series for every EU27 location.

    python -m tourism_pulse_api.ingestion.eurostat_bulk
    python -m tourism_pulse_api.ingestion.eurostat_bulk --only city_tourism
    python -m tourism_pulse_api.ingestion.eurostat_bulk --dry-run

Run after ingestion.eu_locations (it needs the region, area and city
places). Re-running updates values in place.
"""

import argparse
import json
import sys
import urllib.request

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat_bulk.parser import (
    EUROSTAT_SOURCE_NAME,
    POPULATION,
    SERIES,
    Series,
    parse_series,
)
from tourism_pulse_api.ingestion.eurostat_bulk.service import (
    place_index,
    upsert_population,
    upsert_signals,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "tourism-pulse-ingestion/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        return response.read().decode("utf-8")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.eurostat_bulk")
    every: list[Series] = [*SERIES, POPULATION]
    parser.add_argument("--only", choices=[series.key for series in every], action="append")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    selected = [series for series in every if not args.only or series.key in args.only]

    db = SessionLocal()
    failures = 0
    try:
        index = place_index(db)
        for series in selected:
            url = series.url()
            try:
                text = _fetch(url)
                records = parse_series(series, json.loads(text))
            except (OSError, ValueError, KeyError) as exc:
                print(f"[FAILED] {series.key}: {exc}", file=sys.stderr)
                failures += 1
                continue

            if args.dry_run:
                print(f"[DRY RUN] {series.key}: {len(records)} values")
                continue

            observation = archive_raw_observation(
                db,
                source_name=EUROSTAT_SOURCE_NAME,
                dataset=series.dataset,
                raw_payload=text,
                content_type="application/json",
                source_url=url,
            )
            if series is POPULATION:
                summary = upsert_population(
                    db, records, source_observation_id=observation.id, index=index
                )
            else:
                summary = upsert_signals(
                    db,
                    records,
                    kinds=series.kinds,
                    source_url=url,
                    source_observation_id=observation.id,
                    index=index,
                )
            places, unmatched = len(summary.places), len(summary.unmatched_codes)
            print(
                f"[INGESTED] {series.key}: {summary.written} values for {places} places"
                f" ({summary.invalid} invalid, {unmatched} codes without a place)"
            )
    finally:
        db.close()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
