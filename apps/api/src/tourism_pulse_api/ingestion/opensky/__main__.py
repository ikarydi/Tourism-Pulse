"""Reproducible OpenSky airspace-traffic ingestion command.

    python -m tourism_pulse_api.ingestion.opensky --place-id 61 \\
        --lamin 47.35 --lomin 18.90 --lamax 47.65 --lomax 19.20

Works anonymously (no credentials needed) at a lower rate limit/coarser
time resolution. Set OPENSKY_CLIENT_ID/OPENSKY_CLIENT_SECRET in .env (or
pass --client-id/--client-secret) for higher-quota access - create an
API client in your OpenSky account settings at
https://opensky-network.org/.

The bounding box (lamin/lomin/lamax/lomax, decimal degrees) should stay
consistent run-to-run for a given place - the raw aircraft count scales
with the box's area, so changing it between runs makes the signal's
history incomparable to itself (see pulse.airport_traffic).

OpenSky's license is non-commercial - fine for this project's current
research/development stage, but revisit before any commercial use (see
this package's docstring).

Running again never creates a duplicate signal: it overwrites the
place's single current value in place, keyed on
(place_id, signal_type, source) - see service.py's docstring for why.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.opensky.client import (
    TokenRequestError,
    fetch_access_token,
    fetch_states,
)
from tourism_pulse_api.ingestion.opensky.parser import (
    OPENSKY_SOURCE_NAME,
    parse_opensky_states,
)
from tourism_pulse_api.ingestion.opensky.service import (
    build_preview,
    upsert_airport_traffic_signal,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.settings import settings


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.opensky",
        description="Ingest OpenSky airborne-aircraft counts as a transport-activity signal.",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal to.",
    )
    parser.add_argument("--lamin", type=float, required=True, help="Bounding box min latitude.")
    parser.add_argument("--lomin", type=float, required=True, help="Bounding box min longitude.")
    parser.add_argument("--lamax", type=float, required=True, help="Bounding box max latitude.")
    parser.add_argument("--lomax", type=float, required=True, help="Bounding box max longitude.")
    parser.add_argument(
        "--client-id",
        type=str,
        default=None,
        help="Override OPENSKY_CLIENT_ID from the environment/.env.",
    )
    parser.add_argument(
        "--client-secret",
        type=str,
        default=None,
        help="Override OPENSKY_CLIENT_SECRET from the environment/.env.",
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
        help="Read a local OpenSky JSON response instead of fetching (e.g. for testing).",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    client_id = args.client_id or settings.opensky_client_id
    client_secret = args.client_secret or settings.opensky_client_secret

    try:
        if args.json_path is not None:
            with open(args.json_path, encoding="utf-8") as handle:
                text = handle.read()
        else:
            access_token = None
            if client_id and client_secret:
                access_token = fetch_access_token(client_id=client_id, client_secret=client_secret)

            text = fetch_states(
                lamin=args.lamin,
                lomin=args.lomin,
                lamax=args.lamax,
                lomax=args.lomax,
                access_token=access_token,
            )
    except (OSError, TokenRequestError) as exc:
        print(f"Failed to read OpenSky data: {exc}", file=sys.stderr)
        return 1

    try:
        observation = parse_opensky_states(text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    preview = build_preview(observation).as_dict()
    source_url = (
        f"https://opensky-network.org/api/states/all?lamin={args.lamin}"
        f"&lomin={args.lomin}&lamax={args.lamax}&lomax={args.lomax}"
    )

    if args.dry_run:
        print("[DRY RUN]")
        for key, value in preview.items():
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
            source_name=OPENSKY_SOURCE_NAME,
            dataset="opensky_states_all",
            raw_payload=text,
            content_type="application/json",
            place_id=args.place_id,
            source_url=source_url,
        )

        signal, gate = upsert_airport_traffic_signal(
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
            print(f"[REJECTED] {reject_reasons}", file=sys.stderr)
            return 1

        print("[INGESTED]")
        for key, value in preview.items():
            print(f"    {key}: {value}")
        print(f"    signal_id: {signal.id}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
