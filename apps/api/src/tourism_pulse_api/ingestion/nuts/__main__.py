"""Load NUTS region boundaries and assign places their NUTS code.

    python -m tourism_pulse_api.ingestion.nuts
    python -m tourism_pulse_api.ingestion.nuts --dry-run
    python -m tourism_pulse_api.ingestion.nuts --geojson-path NUTS_RG_01M_2024_4326_LEVL_2.geojson

Re-running is safe: regions are upserted by code, and place assignment
simply recomputes every place's code.
"""

import argparse
import sys

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.nuts.client import fetch_nuts_geojson
from tourism_pulse_api.ingestion.nuts.parser import (
    DEFAULT_SCALE,
    DEFAULT_VERSION,
    GISCO_SOURCE_NAME,
    build_geojson_url,
    parse_nuts_geojson,
)
from tourism_pulse_api.ingestion.nuts.service import assign_place_nuts_codes, upsert_regions
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.nuts",
        description="Load NUTS boundaries from GISCO and assign places their NUTS code.",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=2,
        choices=[2, 3],
        help="2 sets places' NUTS 2 (and national) codes, 3 their NUTS 3 codes.",
    )
    parser.add_argument("--version", default=DEFAULT_VERSION, help="NUTS version, e.g. 2024.")
    parser.add_argument("--scale", default=DEFAULT_SCALE, help="GISCO scale, e.g. 01M.")
    parser.add_argument("--dry-run", action="store_true", help="Parse only; write nothing.")
    parser.add_argument(
        "--geojson-path", default=None, help="Read a local GISCO GeoJSON file instead."
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    source_url = build_geojson_url(level=args.level, version=args.version, scale=args.scale)

    try:
        if args.geojson_path:
            with open(args.geojson_path, encoding="utf-8") as handle:
                text = handle.read()
        else:
            text = fetch_nuts_geojson(level=args.level, version=args.version, scale=args.scale)
        features = parse_nuts_geojson(text, version=args.version)
    except (OSError, ValueError) as exc:
        print(f"Failed to load NUTS boundaries: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"[DRY RUN] {len(features)} NUTS {args.level} regions (NUTS {args.version})")
        return 0

    db = SessionLocal()
    try:
        archive_raw_observation(
            db,
            source_name=GISCO_SOURCE_NAME,
            dataset=f"nuts_{args.version}_levl_{args.level}",
            raw_payload=text,
            content_type="application/geo+json",
            source_url=source_url,
        )
        loaded = upsert_regions(db, features)
        result = assign_place_nuts_codes(db, level=args.level)
    finally:
        db.close()

    print(f"[INGESTED] {loaded} NUTS {args.level} regions (NUTS {args.version})")
    print(f"    destinations assigned: {result.destinations_assigned}")
    print(f"    countries assigned: {result.countries_assigned}")
    if result.destinations_unmatched:
        print(f"    unmatched destinations: {', '.join(result.destinations_unmatched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
