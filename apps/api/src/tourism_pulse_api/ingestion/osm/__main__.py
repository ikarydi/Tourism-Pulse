"""Reproducible OpenStreetMap hotel/restaurant ingestion command.

    python -m tourism_pulse_api.ingestion.osm --place-id 61 --lat 47.4979 --lon 19.0402 --category hotel
    python -m tourism_pulse_api.ingestion.osm --place-id 61 --lat 47.4979 --lon 19.0402 --category restaurant --dry-run
    python -m tourism_pulse_api.ingestion.osm --place-id 61 --lat 47.4979 --lon 19.0402 --category hotel --radius-km 15

Like the weather adapter, coordinates are passed explicitly rather than
looked up from a place-name table - this adapter has no hardcoded place
list and works for any place you give coordinates for.

`--category` selects which POI type to ingest (default: hotel):

    hotel        tourism=hotel     - feeds `capacity` via `hotel_count`
    restaurant   amenity=restaurant - feeds `capacity` via `restaurant_count`

Each run does two things: writes one Attraction row per POI found (the
display/"digital twin" layer), and overwrites the place's single current
POI-count Signal for this category (the Pulse-facing layer) - see
service.py's docstring for why this overwrites in place rather than
accumulating a new row per run.

Overpass (OSM's free query API) is a live snapshot, not a published
series - there is no --month/--backfill the way KSH/Eurostat have.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.osm.client import DEFAULT_RADIUS_METERS, fetch_pois
from tourism_pulse_api.ingestion.osm.parser import (
    CATEGORY_TAG_QUERIES,
    OSM_SOURCE_NAME,
    parse_overpass_pois,
    parse_overpass_timestamp,
)
from tourism_pulse_api.ingestion.osm.service import (
    build_preview,
    upsert_attraction,
    upsert_poi_count_signal,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.pulse.poi_density import (
    HOTEL_REFERENCE_COUNT,
    RESTAURANT_REFERENCE_COUNT,
)

_REFERENCE_COUNTS: dict[str, int] = {
    "hotel": HOTEL_REFERENCE_COUNT,
    "restaurant": RESTAURANT_REFERENCE_COUNT,
}


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.osm",
        description="Ingest hotel/restaurant POIs from OpenStreetMap as Attractions + a capacity signal.",
    )
    parser.add_argument("--place-id", type=int, required=True, help="Place to attach the ingested data to.")
    parser.add_argument("--lat", type=float, required=True, help="Latitude of the place.")
    parser.add_argument("--lon", type=float, required=True, help="Longitude of the place.")
    parser.add_argument(
        "--category",
        type=str,
        default="hotel",
        choices=sorted(CATEGORY_TAG_QUERIES),
        help="Which POI type to ingest (default: hotel).",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=DEFAULT_RADIUS_METERS / 1000,
        help=f"Search radius in kilometers (default: {DEFAULT_RADIUS_METERS / 1000:g}).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would be ingested without writing to the database.")
    parser.add_argument("--json-path", type=str, default=None, help="Read a local Overpass JSON response instead of fetching (e.g. for testing).")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.json_path is not None:
        with open(args.json_path, encoding="utf-8") as handle:
            text = handle.read()
    else:
        try:
            text = fetch_pois(
                category=args.category,
                latitude=args.lat,
                longitude=args.lon,
                radius_meters=int(args.radius_km * 1000),
            )
        except OSError as exc:
            print(f"Failed to reach Overpass: {exc}", file=sys.stderr)
            return 1

    try:
        pois = parse_overpass_pois(text, category=args.category)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    observed_at = parse_overpass_timestamp(text)
    reference_count = _REFERENCE_COUNTS[args.category]
    preview = build_preview(pois, category=args.category, reference_count=reference_count)

    if args.dry_run:
        print(f"[DRY RUN] {args.category}")
        for key, value in preview.as_dict().items():
            print(f"    {key}: {value}")
        return 0

    if not pois:
        print(f"No {args.category} POIs found within the search radius - nothing to ingest.", file=sys.stderr)
        return 1

    db = SessionLocal()

    try:
        place = db.get(Place, args.place_id)

        if place is None:
            print(f"Place {args.place_id} not found.", file=sys.stderr)
            return 1

        created_count = 0
        for poi in pois:
            _, created = upsert_attraction(db, place_id=args.place_id, poi=poi)
            created_count += 1 if created else 0

        source_observation = archive_raw_observation(
            db,
            source_name=OSM_SOURCE_NAME,
            dataset=f"overpass_{args.category}",
            raw_payload=text,
            content_type="application/json",
            place_id=args.place_id,
        )

        signal, gate = upsert_poi_count_signal(
            db,
            place_id=args.place_id,
            category=args.category,
            poi_count=len(pois),
            observed_at=observed_at,
            source_observation_id=source_observation.id,
        )

        print(f"[INGESTED] {args.category}")
        print(f"    poi_count: {len(pois)}")
        print(f"    attractions_created: {created_count}")
        print(f"    attractions_updated: {len(pois) - created_count}")

        if signal is None:
            reject_reasons = "; ".join(
                outcome.detail or outcome.check_name
                for outcome in gate.outcomes
                if not outcome.passed and outcome.severity == "reject"
            )
            print(f"    count_signal: REJECTED ({reject_reasons})", file=sys.stderr)
        else:
            print(f"    count_signal_id: {signal.id}")
            print(f"    normalized_value: {preview.normalized_value}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
