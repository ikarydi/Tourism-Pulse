"""Ingest Eurostat regional tourism-pressure indicators for all regions.

    python -m tourism_pulse_api.ingestion.eurostat_regional
    python -m tourism_pulse_api.ingestion.eurostat_regional --dry-run

Annual data; re-running overwrites values in place (Eurostat revises).
"""

import argparse
import json
import sys

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat_regional.client import fetch_dataset
from tourism_pulse_api.ingestion.eurostat_regional.parser import (
    EUROSTAT_SOURCE_NAME,
    NIGHTS_REGIONAL_DATASET,
    NIGHTS_REGIONAL_MONTHLY_DATASET,
    dataset_url,
    parse_intensity_density,
    parse_seasonality,
)
from tourism_pulse_api.ingestion.eurostat_regional.service import upsert_indicators
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation

DEFAULT_SINCE_YEAR = 2019

DATASETS = (
    (NIGHTS_REGIONAL_DATASET, ("P_THAB", "P_KM2"), parse_intensity_density),
    (NIGHTS_REGIONAL_MONTHLY_DATASET, ("NR",), parse_seasonality),
)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.eurostat_regional",
        description="Ingest Eurostat regional tourism-pressure indicators.",
    )
    parser.add_argument("--since-year", type=int, default=DEFAULT_SINCE_YEAR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    fetched = []
    for dataset, units, parse in DATASETS:
        url = dataset_url(dataset, units=units, since_year=args.since_year)
        try:
            text = fetch_dataset(url)
            values = parse(json.loads(text))
        except (OSError, ValueError) as exc:
            print(f"Failed to load {dataset}: {exc}", file=sys.stderr)
            return 1
        fetched.append((dataset, url, text, values))

    if args.dry_run:
        for dataset, _url, _text, values in fetched:
            regions = len({value.nuts_code for value in values})
            print(f"[DRY RUN] {dataset}: {len(values)} values, {regions} regions")
        return 0

    db = SessionLocal()
    try:
        for dataset, url, text, values in fetched:
            observation = archive_raw_observation(
                db,
                source_name=EUROSTAT_SOURCE_NAME,
                dataset=dataset,
                raw_payload=text,
                content_type="application/json",
                source_url=url,
            )
            written = upsert_indicators(db, values, source_observation_id=observation.id)
            print(f"[INGESTED] {dataset}: {written} indicator values")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
