"""Reproducible current-weather ingestion command (Open-Meteo).

    python -m tourism_pulse_api.ingestion.weather --place-id 61 --lat 47.4979 --lon 19.0402
    python -m tourism_pulse_api.ingestion.weather --place-id 61 --lat 47.4979 --lon 19.0402 --dry-run

Unlike the KSH commands, this is a live source: each run fetches *current*
conditions (not a historical series), so there is no --month/--backfill.
Coordinates are passed explicitly rather than looked up from a place-name
table, so this adapter has no hardcoded place list - it works for any place
you give coordinates for.

Running twice within the same measurement interval never creates a
duplicate signal: it upserts in place, keyed on
(place_id, signal_type, observed_at, source). Running again once conditions
have actually moved to a new interval creates fresh rows, as expected for a
live signal.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.weather.client import fetch_current_weather
from tourism_pulse_api.ingestion.weather.parser import (
    OPEN_METEO_BASE_URL,
    build_request_url,
    parse_open_meteo_current,
)
from tourism_pulse_api.ingestion.weather.service import build_preview, upsert_weather_signals


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.weather",
        description="Ingest current weather (Open-Meteo) as weather signals for a place.",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal(s) to.",
    )
    parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Latitude of the place.",
    )
    parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="Longitude of the place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested without writing to the database.",
    )
    parser.add_argument(
        "--json-path",
        type=str,
        default=None,
        help="Read a local Open-Meteo JSON response instead of fetching (e.g. for testing).",
    )
    return parser


def _load_response_text(*, lat: float, lon: float, json_path: str | None) -> str:
    if json_path is not None:
        with open(json_path, encoding="utf-8") as handle:
            return handle.read()

    return fetch_current_weather(latitude=lat, longitude=lon)


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        text = _load_response_text(lat=args.lat, lon=args.lon, json_path=args.json_path)
    except OSError as exc:
        print(f"Failed to read weather data: {exc}", file=sys.stderr)
        return 1

    try:
        observation = parse_open_meteo_current(text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    preview = build_preview(observation).as_dict()
    source_url = build_request_url(latitude=args.lat, longitude=args.lon, base_url=OPEN_METEO_BASE_URL)

    if args.dry_run:
        print(f"[DRY RUN] {preview['observed_at']}")
        for key, value in preview.items():
            if key == "observed_at":
                continue
            print(f"    {key}: {value}")
        return 0

    db = SessionLocal()

    try:
        place = db.get(Place, args.place_id)

        if place is None:
            print(f"Place {args.place_id} not found.", file=sys.stderr)
            return 1

        results = upsert_weather_signals(
            db,
            place_id=args.place_id,
            observation=observation,
            source_url=source_url,
        )

        print(f"[INGESTED] {preview['observed_at']}")
        for key, value in preview.items():
            if key == "observed_at":
                continue
            print(f"    {key}: {value}")
        for signal, created in results:
            action = "created" if created else "updated"
            print(f"    signal[{signal.signal_type}]: id={signal.id} ({action})")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
