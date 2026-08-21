"""Reproducible events ingestion command (Ticketmaster Discovery API).

    python -m tourism_pulse_api.ingestion.events --place-id 61 --city Budapest --country-code HU
    python -m tourism_pulse_api.ingestion.events --place-id 61 --city Budapest \
        --country-code HU --dry-run

Requires an API key: set TICKETMASTER_API_KEY in .env (free signup at
https://developer.ticketmaster.com/), or pass --api-key explicitly.

Like weather, this is a live source with no hardcoded place list -
coordinates/city are supplied explicitly per run, not looked up from a
table baked into production code.

By default, fetches upcoming events (from now) for the given city. Running
again never creates duplicates: it upserts in place, keyed on
(source, external_id) - Ticketmaster's own event ID.
"""

import argparse
import sys
from datetime import UTC, datetime

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.events.client import build_public_source_url, fetch_events
from tourism_pulse_api.ingestion.events.parser import parse_ticketmaster_events
from tourism_pulse_api.ingestion.events.service import build_preview, upsert_events
from tourism_pulse_api.settings import settings


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.events",
        description="Ingest upcoming events from Ticketmaster for a place.",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested event(s) to.",
    )
    parser.add_argument(
        "--city",
        type=str,
        required=True,
        help="City to search (Ticketmaster's city filter).",
    )
    parser.add_argument(
        "--country-code",
        type=str,
        required=True,
        help="ISO country code (e.g. HU).",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=50,
        help="Maximum number of events to fetch (default: 50).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested without writing to the database.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Override TICKETMASTER_API_KEY from the environment/.env.",
    )
    parser.add_argument(
        "--json-path",
        type=str,
        default=None,
        help="Read a local Ticketmaster JSON response instead of fetching (e.g. for testing).",
    )
    return parser


def _load_response_text(
    *,
    api_key: str | None,
    city: str,
    country_code: str,
    size: int,
    json_path: str | None,
) -> str:
    if json_path is not None:
        with open(json_path, encoding="utf-8") as handle:
            return handle.read()

    if not api_key:
        raise ValueError(
            "No Ticketmaster API key configured. Set TICKETMASTER_API_KEY in "
            ".env or pass --api-key."
        )

    return fetch_events(
        api_key=api_key,
        city=city,
        country_code=country_code,
        start_date_time=datetime.now(UTC),
        size=size,
    )


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    api_key = args.api_key or settings.ticketmaster_api_key

    try:
        text = _load_response_text(
            api_key=api_key,
            city=args.city,
            country_code=args.country_code,
            size=args.size,
            json_path=args.json_path,
        )
    except (OSError, ValueError) as exc:
        print(f"Failed to read events data: {exc}", file=sys.stderr)
        return 1

    try:
        events = parse_ticketmaster_events(text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not events:
        print("No upcoming events with a confirmed date found.", file=sys.stderr)
        return 0

    source_url = build_public_source_url(
        city=args.city,
        country_code=args.country_code,
        start_date_time=datetime.now(UTC),
        size=args.size,
    )

    if args.dry_run:
        for event in events:
            preview = build_preview(event).as_dict()
            print(f"[DRY RUN] {preview['name']}")
            for key, value in preview.items():
                if key == "name":
                    continue
                print(f"    {key}: {value}")
            print()
        return 0

    db = SessionLocal()

    try:
        place = db.get(Place, args.place_id)

        if place is None:
            print(f"Place {args.place_id} not found.", file=sys.stderr)
            return 1

        results = upsert_events(
            db,
            place_id=args.place_id,
            events=events,
            source_url=source_url,
        )

        created_count = sum(1 for _, created in results if created)
        updated_count = len(results) - created_count

        for event, created in results:
            action = "created" if created else "updated"
            start = event.start_at.isoformat()
            print(f"[INGESTED] id={event.id} ({action}): {event.name} @ {start}")

        print(f"\n{created_count} created, {updated_count} updated.")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
