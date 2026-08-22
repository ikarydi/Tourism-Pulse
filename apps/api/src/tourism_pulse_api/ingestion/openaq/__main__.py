"""Reproducible OpenAQ air-quality ingestion command.

    python -m tourism_pulse_api.ingestion.openaq --place-id 61 --lat 47.4979 --lon 19.0402
    python -m tourism_pulse_api.ingestion.openaq --place-id 61 \
        --lat 47.4979 --lon 19.0402 --dry-run

Requires an API key: set OPENAQ_API_KEY in .env (register at
https://explore.openaq.org/register), or pass --api-key explicitly.

Like weather/GDACS, coordinates are supplied explicitly per run - no
hardcoded place list.

Running again never creates a duplicate signal: it overwrites the
place's single current air_quality_pm25 value in place, keyed on
(place_id, signal_type, source) - see service.py's docstring for why.

Two HTTP calls per real run (nearest-station search, then that
station's latest reading) - see the package docstring for why they
can't be combined into one.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.openaq.client import (
    DEFAULT_RADIUS_METERS,
    build_latest_url,
    fetch_latest_measurements,
    fetch_nearest_locations,
)
from tourism_pulse_api.ingestion.openaq.parser import (
    OPENAQ_SOURCE_NAME,
    parse_openaq_latest,
    parse_openaq_locations,
)
from tourism_pulse_api.ingestion.openaq.service import (
    build_preview,
    upsert_air_quality_signal,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.settings import settings


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.openaq",
        description="Ingest OpenAQ PM2.5 readings as an environment signal for a place.",
    )
    parser.add_argument("--place-id", type=int, required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument(
        "--radius-meters",
        type=int,
        default=DEFAULT_RADIUS_METERS,
        help=f"Search radius in meters, max 25000 (default: {DEFAULT_RADIUS_METERS}).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Override OPENAQ_API_KEY from the environment/.env.",
    )
    parser.add_argument(
        "--locations-json-path",
        type=str,
        default=None,
        help="Read a local /locations JSON response instead of fetching (e.g. for testing).",
    )
    parser.add_argument(
        "--latest-json-path",
        type=str,
        default=None,
        help=(
            "Read a local /locations/{id}/latest JSON response instead of "
            "fetching (used together with --locations-json-path)."
        ),
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    api_key = args.api_key or settings.openaq_api_key

    if args.locations_json_path is not None:
        with open(args.locations_json_path, encoding="utf-8") as handle:
            locations_text = handle.read()
    else:
        if not api_key:
            print(
                "No OpenAQ API key configured. Set OPENAQ_API_KEY in .env or "
                "pass --api-key.",
                file=sys.stderr,
            )
            return 1
        try:
            locations_text = fetch_nearest_locations(
                api_key=api_key,
                latitude=args.lat,
                longitude=args.lon,
                radius_meters=args.radius_meters,
            )
        except OSError as exc:
            print(f"Failed to read OpenAQ locations data: {exc}", file=sys.stderr)
            return 1

    try:
        locations = parse_openaq_locations(locations_text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    location = next((loc for loc in locations if loc.pm25_sensor_id is not None), None)

    if location is None:
        print(
            f"No PM2.5 monitoring station found within {args.radius_meters}m.",
            file=sys.stderr,
        )
        return 1

    if args.latest_json_path is not None:
        with open(args.latest_json_path, encoding="utf-8") as handle:
            latest_text = handle.read()
    else:
        if not api_key:
            print(
                "No OpenAQ API key configured. Set OPENAQ_API_KEY in .env or "
                "pass --api-key.",
                file=sys.stderr,
            )
            return 1
        try:
            latest_text = fetch_latest_measurements(
                api_key=api_key, location_id=location.id
            )
        except OSError as exc:
            print(f"Failed to read OpenAQ latest-measurement data: {exc}", file=sys.stderr)
            return 1

    try:
        observation = parse_openaq_latest(latest_text, location=location)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if observation is None:
        print(
            f"No fresh PM2.5 reading available for station {location.name!r}.",
            file=sys.stderr,
        )
        return 1

    preview = build_preview(observation).as_dict()
    source_url = build_latest_url(location_id=location.id)

    if args.dry_run:
        print(f"[DRY RUN] {location.name!r}")
        for key, value in preview.items():
            if key == "location_name":
                continue
            print(f"    {key}: {value}")
        return 0

    db = SessionLocal()

    try:
        place = db.get(Place, args.place_id)

        if place is None:
            print(f"Place {args.place_id} not found.", file=sys.stderr)
            return 1

        archive_raw_observation(
            db,
            source_name=OPENAQ_SOURCE_NAME,
            dataset="openaq_locations",
            raw_payload=locations_text,
            content_type="application/json",
            place_id=args.place_id,
        )

        source_observation = archive_raw_observation(
            db,
            source_name=OPENAQ_SOURCE_NAME,
            dataset="openaq_latest",
            raw_payload=latest_text,
            content_type="application/json",
            place_id=args.place_id,
            source_url=source_url,
        )

        signal, gate = upsert_air_quality_signal(
            db,
            place_id=args.place_id,
            observation=observation,
            source_url=source_url,
            source_observation_id=source_observation.id,
        )

        if signal is None:
            reject_reasons = "; ".join(
                outcome.detail or outcome.check_name
                for outcome in gate.outcomes
                if not outcome.passed and outcome.severity == "reject"
            )
            print(f"[REJECTED] {location.name!r}: {reject_reasons}", file=sys.stderr)
            return 1

        print(f"[INGESTED] {location.name!r}")
        for key, value in preview.items():
            if key == "location_name":
                continue
            print(f"    {key}: {value}")
        print(f"    signal_id: {signal.id}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
