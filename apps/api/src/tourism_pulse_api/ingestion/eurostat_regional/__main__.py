"""Ingest Eurostat regional tourism-pressure indicators for all regions.

    python -m tourism_pulse_api.ingestion.eurostat_regional
    python -m tourism_pulse_api.ingestion.eurostat_regional --dry-run

Annual data; re-running overwrites values in place (Eurostat revises).
Four datasets: official nights (intensity, density, and absolute nights
for the short-term-rental share), official monthly nights (seasonality),
and platform-booked nights at NUTS 1/2 and NUTS 3.
"""

import argparse
import json
import sys
from dataclasses import dataclass

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat_regional.client import fetch_dataset
from tourism_pulse_api.ingestion.eurostat_regional.parser import (
    EUROSTAT_SOURCE_NAME,
    NIGHTS_REGIONAL_DATASET,
    NIGHTS_REGIONAL_MONTHLY_DATASET,
    OFFICIAL_SCOPE,
    PLATFORM_NUTS3_DATASET,
    PLATFORM_NUTS12_DATASET,
    PLATFORM_SCOPE,
    IndicatorValue,
    dataset_url,
    parse_intensity_density,
    parse_nights,
    parse_seasonality,
    str_share,
)
from tourism_pulse_api.ingestion.eurostat_regional.service import upsert_indicators
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation

DEFAULT_SINCE_YEAR = 2019


@dataclass
class Fetched:
    dataset: str
    url: str
    text: str
    payload: dict
    values: list[IndicatorValue]


def _requests(since_year: int) -> list[tuple[str, str]]:
    return [
        (
            NIGHTS_REGIONAL_DATASET,
            dataset_url(
                NIGHTS_REGIONAL_DATASET,
                filters={**OFFICIAL_SCOPE, "unit": ("P_THAB", "P_KM2", "NR")},
                since_year=since_year,
            ),
        ),
        (
            NIGHTS_REGIONAL_MONTHLY_DATASET,
            dataset_url(
                NIGHTS_REGIONAL_MONTHLY_DATASET,
                filters={**OFFICIAL_SCOPE, "unit": "NR"},
                since_year=since_year,
            ),
        ),
        (
            PLATFORM_NUTS12_DATASET,
            dataset_url(
                PLATFORM_NUTS12_DATASET,
                filters={**PLATFORM_SCOPE, "month": "TOTAL"},
                since_year=since_year,
            ),
        ),
        (
            PLATFORM_NUTS3_DATASET,
            dataset_url(PLATFORM_NUTS3_DATASET, filters=PLATFORM_SCOPE, since_year=since_year),
        ),
    ]


def _derive(fetched: dict[str, Fetched]) -> None:
    """Fill each dataset's indicator values; the STR share joins official
    nights with platform nights and is attributed to the platform dataset
    it came from."""
    official = fetched[NIGHTS_REGIONAL_DATASET]
    official.values = parse_intensity_density(official.payload)
    monthly = fetched[NIGHTS_REGIONAL_MONTHLY_DATASET]
    monthly.values = parse_seasonality(monthly.payload)

    official_nights = parse_nights(official.payload)
    for dataset in (PLATFORM_NUTS12_DATASET, PLATFORM_NUTS3_DATASET):
        platform = fetched[dataset]
        platform.values = str_share(official_nights, parse_nights(platform.payload))


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.eurostat_regional",
        description="Ingest Eurostat regional tourism-pressure indicators.",
    )
    parser.add_argument("--since-year", type=int, default=DEFAULT_SINCE_YEAR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    fetched: dict[str, Fetched] = {}
    for dataset, url in _requests(args.since_year):
        try:
            text = fetch_dataset(url)
            fetched[dataset] = Fetched(dataset, url, text, json.loads(text), [])
        except (OSError, ValueError) as exc:
            print(f"Failed to load {dataset}: {exc}", file=sys.stderr)
            return 1

    try:
        _derive(fetched)
    except ValueError as exc:
        print(f"Failed to parse Eurostat regional data: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        for item in fetched.values():
            regions = len({value.nuts_code for value in item.values})
            print(f"[DRY RUN] {item.dataset}: {len(item.values)} values, {regions} regions")
        return 0

    db = SessionLocal()
    try:
        for item in fetched.values():
            observation = archive_raw_observation(
                db,
                source_name=EUROSTAT_SOURCE_NAME,
                dataset=item.dataset,
                raw_payload=item.text,
                content_type="application/json",
                source_url=item.url,
            )
            written = upsert_indicators(db, item.values, source_observation_id=observation.id)
            print(f"[INGESTED] {item.dataset}: {written} indicator values")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
