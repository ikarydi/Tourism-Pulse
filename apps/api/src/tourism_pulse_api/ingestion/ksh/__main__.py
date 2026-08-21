"""Reproducible KSH tourism-nights ingestion command.

    python -m tourism_pulse_api.ingestion.ksh --place-id 61
    python -m tourism_pulse_api.ingestion.ksh --place-id 61 --dry-run
    python -m tourism_pulse_api.ingestion.ksh --place-id 61 --month 2026-06
    python -m tourism_pulse_api.ingestion.ksh --place-id 61 --backfill
    python -m tourism_pulse_api.ingestion.ksh --place-id 70 --region debrecen

`--region` selects which KSH tourism area to ingest (default: budapest) -
see `parser.SUPPORTED_REGIONS` for every area KSH publishes. One place maps
to one region per run; ingesting several regions means running this command
once per place/region pair.

By default, a run ingests only the single most recently published month
(matching how this command would run on a recurring schedule). Pass
--backfill once to load the full available history for a place, which is
also what the seasonal normalization needs to compute a real baseline
instead of reporting "insufficient_baseline".

Running the same period twice never creates a duplicate signal: it upserts
in place, keyed on (place_id, signal_type, observed_at, source).
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.ksh.client import fetch_ksh_csv
from tourism_pulse_api.ingestion.ksh.parser import (
    DEFAULT_REGION,
    KSH_CSV_URL,
    SUPPORTED_REGIONS,
    parse_ksh_csv,
)
from tourism_pulse_api.ingestion.ksh.service import (
    build_preview,
    select_observations,
    upsert_tourism_nights_signal,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.ksh",
        description=(
            "Ingest tourism-nights data from KSH STADAT 27.2.1.19 "
            "as tourism_nights signals."
        ),
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal(s) to.",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=DEFAULT_REGION,
        choices=sorted(SUPPORTED_REGIONS),
        help="KSH tourism area to ingest for this place (default: budapest).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested without writing to the database.",
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Ingest a single YYYY-MM period instead of the latest one.",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Ingest every available published month, not just the latest.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=KSH_CSV_URL,
        help="Override the KSH CSV URL.",
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=None,
        help="Read a local CSV file instead of downloading (e.g. for testing).",
    )
    return parser


def _load_csv_text(*, url: str, csv_path: str | None) -> str:
    if csv_path is not None:
        with open(csv_path, encoding="iso-8859-2") as handle:
            return handle.read()

    return fetch_ksh_csv(url)


def _print_preview(preview: dict[str, object], *, prefix: str) -> None:
    print(f"{prefix} {preview['period']}")
    for key, value in preview.items():
        if key == "period":
            continue
        print(f"    {key}: {value}")
    print()


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        text = _load_csv_text(url=args.url, csv_path=args.csv_path)
    except OSError as exc:
        print(f"Failed to read KSH data: {exc}", file=sys.stderr)
        return 1

    observations = parse_ksh_csv(text, regions=[args.region])

    if not observations:
        print(
            f"No {args.region!r} tourism-nights observations found in the KSH dataset.",
            file=sys.stderr,
        )
        return 1

    try:
        targets = select_observations(
            observations,
            month=args.month,
            backfill=args.backfill,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not targets:
        print(f"No observation found for period {args.month!r}.", file=sys.stderr)
        return 1

    if args.dry_run:
        for observation in targets:
            preview = build_preview(observation, observations).as_dict()
            _print_preview(preview, prefix="[DRY RUN]")
        return 0

    db = SessionLocal()

    try:
        place = db.get(Place, args.place_id)

        if place is None:
            print(f"Place {args.place_id} not found.", file=sys.stderr)
            return 1

        for observation in targets:
            preview = build_preview(observation, observations).as_dict()

            signal, created = upsert_tourism_nights_signal(
                db,
                place_id=args.place_id,
                observation=observation,
                source_url=args.url,
            )

            preview["signal_id"] = signal.id
            preview["action"] = "created" if created else "updated"

            _print_preview(preview, prefix="[INGESTED]")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
