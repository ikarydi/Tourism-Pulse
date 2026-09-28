"""Create places for every EU27 region, area and city with tourism data.

    python -m tourism_pulse_api.ingestion.eu_locations
    python -m tourism_pulse_api.ingestion.eu_locations --dry-run

Needs NUTS 2 and NUTS 3 boundaries (ingestion.nuts --level 2 / --level 3)
and regional indicators (ingestion.eurostat_regional) loaded first.
"""

import argparse
import json
import sys
import urllib.request

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eu_locations.parser import (
    CITY_TOURISM_URL,
    GISCO_SOURCE_NAME,
    URAU_POINTS_URL,
    cities_with_tourism_data,
    parse_city_points,
)
from tourism_pulse_api.ingestion.eu_locations.service import (
    LocationSummary,
    ensure_city_places,
    ensure_ksh_area_places,
    ensure_region_places,
)
from tourism_pulse_api.ingestion.nuts.service import assign_place_nuts_codes
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "tourism-pulse-ingestion/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read().decode("utf-8")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.eu_locations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        points_text = _fetch(URAU_POINTS_URL)
        points = parse_city_points(points_text)
        with_data = cities_with_tourism_data(json.loads(_fetch(CITY_TOURISM_URL)))
    except (OSError, ValueError, KeyError) as exc:
        print(f"Failed to load city data: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        eligible = sum(point.code in with_data for point in points)
        print(f"[DRY RUN] {len(points)} EU27 city points, {eligible} with tourism data")
        return 0

    summary = LocationSummary()
    db = SessionLocal()
    try:
        archive_raw_observation(
            db,
            source_name=GISCO_SOURCE_NAME,
            dataset="urau_2021_city_points",
            raw_payload=points_text,
            content_type="application/geo+json",
            source_url=URAU_POINTS_URL,
        )
        ensure_region_places(db, summary)
        ensure_ksh_area_places(db, summary)
        ensure_city_places(db, points, with_data, summary)
        # Cities and new curated places get their NUTS 2 / NUTS 3 codes.
        assign_place_nuts_codes(db, level=2)
        assign_place_nuts_codes(db, level=3)
    finally:
        db.close()

    print(f"[INGESTED] regions (NUTS 2): {summary.regions}, areas (NUTS 3): {summary.areas}")
    linked = len(summary.cities_linked)
    print(f"    cities created: {summary.cities_created}, linked to curated: {linked}")
    print(f"    KSH tourism areas added: {summary.ksh_areas}")
    if summary.cities_linked:
        print(f"    linked: {', '.join(summary.cities_linked)}")
    if summary.skipped_no_country:
        print(f"    skipped (no country place): {', '.join(sorted(summary.skipped_no_country))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
