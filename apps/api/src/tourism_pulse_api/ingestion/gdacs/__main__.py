"""Reproducible GDACS disaster-alert ingestion command.

    python -m tourism_pulse_api.ingestion.gdacs --place-id 61 --country HU
    python -m tourism_pulse_api.ingestion.gdacs --place-id 61 --country HU --dry-run

No API key required - GDACS's event-list endpoint is fully public and
keyless (see the package docstring).

Like Eurostat, the country code is supplied explicitly per run (not
looked up from Destination.country_code) - this is a live source with
no hardcoded place list, consistent with every other adapter in this
codebase (spec section 50 rule 4: never hardcode external source data
into production logic).

Running again never creates a duplicate signal: it overwrites the
place's single current disaster_alert_severity value in place, keyed on
(place_id, signal_type, source) - see service.py's docstring for why.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.gdacs.client import build_request_url, fetch_events
from tourism_pulse_api.ingestion.gdacs.parser import (
    GDACS_SOURCE_NAME,
    parse_gdacs_events,
)
from tourism_pulse_api.ingestion.gdacs.service import (
    build_preview,
    upsert_disaster_alert_severity_signal,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.gdacs",
        description="Ingest GDACS disaster-alert severity as a risk signal for a place.",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal to.",
    )
    parser.add_argument(
        "--country",
        type=str,
        required=True,
        help="ISO 3166-1 alpha-2 country code, e.g. HU.",
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
        help="Read a local GDACS JSON response instead of fetching (e.g. for testing).",
    )
    return parser


def _load_response_text(
    *,
    country: str,
    json_path: str | None,
) -> str:
    if json_path is not None:
        with open(json_path, encoding="utf-8") as handle:
            return handle.read()

    return fetch_events(country=country)


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        text = _load_response_text(country=args.country, json_path=args.json_path)
    except OSError as exc:
        print(f"Failed to read GDACS data: {exc}", file=sys.stderr)
        return 1

    try:
        observation = parse_gdacs_events(text, country=args.country)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    preview = build_preview(observation).as_dict()
    source_url = build_request_url(country=args.country)

    if args.dry_run:
        print(f"[DRY RUN] {args.country!r}")
        for key, value in preview.items():
            if key == "country":
                continue
            print(f"    {key}: {value}")
        return 0

    db = SessionLocal()

    try:
        place = db.get(Place, args.place_id)

        if place is None:
            print(f"Place {args.place_id} not found.", file=sys.stderr)
            return 1

        source_observation = archive_raw_observation(
            db,
            source_name=GDACS_SOURCE_NAME,
            dataset="gdacs_events",
            raw_payload=text,
            content_type="application/json",
            place_id=args.place_id,
            source_url=source_url,
        )

        signal, gate = upsert_disaster_alert_severity_signal(
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
            print(f"[REJECTED] {args.country!r}: {reject_reasons}", file=sys.stderr)
            return 1

        print(f"[INGESTED] {args.country!r}")
        for key, value in preview.items():
            if key == "country":
                continue
            print(f"    {key}: {value}")
        print(f"    signal_id: {signal.id}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
