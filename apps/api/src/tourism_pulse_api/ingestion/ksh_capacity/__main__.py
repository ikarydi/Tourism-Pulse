"""Reproducible KSH accommodation-capacity ingestion command.

    python -m tourism_pulse_api.ingestion.ksh_capacity --place-id 347
    python -m tourism_pulse_api.ingestion.ksh_capacity --place-id 347 --dry-run
    python -m tourism_pulse_api.ingestion.ksh_capacity --place-id 347 --month 2026-06
    python -m tourism_pulse_api.ingestion.ksh_capacity --place-id 347 --backfill
    python -m tourism_pulse_api.ingestion.ksh_capacity --place-id 347 --metric bedrooms

Unlike KSH tourism-nights, this table has no regional breakdown - it is a
single Hungary-wide series, so it is meant to be ingested once, against a
national-level place (not the region-specific ones tourism_nights uses).

`--metric` selects which capacity figure to ingest (default: bed_places -
the headline "how many people can we accommodate" number). See
`parser.SUPPORTED_METRICS` for the others (units, bedrooms).

By default, a run ingests only the single most recently published month.
Pass --backfill once to load the full available history for a place, which
is also what the seasonal normalization needs to compute a real baseline
instead of reporting "insufficient_baseline".

Running the same period twice never creates a duplicate signal: it upserts
in place, keyed on (place_id, signal_type, observed_at, source).
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.ksh_capacity.client import fetch_ksh_capacity_csv
from tourism_pulse_api.ingestion.ksh_capacity.parser import (
    DEFAULT_METRIC,
    KSH_CSV_URL,
    KSH_SOURCE_NAME,
    KSH_TABLE_ID,
    SUPPORTED_METRICS,
    parse_ksh_capacity_csv,
)
from tourism_pulse_api.ingestion.ksh_capacity.service import (
    build_preview,
    select_observations,
    upsert_capacity_signal,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.ksh_capacity",
        description=(
            "Ingest Hungary-wide accommodation capacity from KSH STADAT "
            "27.2.1.13 as accommodation_capacity signals."
        ),
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal(s) to (a national-level place).",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default=DEFAULT_METRIC,
        choices=sorted(SUPPORTED_METRICS),
        help="Which capacity figure to ingest (default: bed_places).",
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

    return fetch_ksh_capacity_csv(url)


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

    try:
        observations = parse_ksh_capacity_csv(text, metric=args.metric)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not observations:
        print(
            f"No {args.metric!r} capacity observations found in the KSH dataset.",
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

        source_observation = archive_raw_observation(
            db,
            source_name=KSH_SOURCE_NAME,
            dataset=f"ksh_stadat_{KSH_TABLE_ID.replace('.', '_')}",
            raw_payload=text,
            content_type="text/csv",
            place_id=args.place_id,
            source_url=args.url,
        )

        for observation in targets:
            preview = build_preview(observation, observations).as_dict()

            signal, created, gate = upsert_capacity_signal(
                db,
                place_id=args.place_id,
                observation=observation,
                source_url=args.url,
                source_observation_id=source_observation.id,
            )

            if signal is None:
                reject_reasons = "; ".join(
                    outcome.detail or outcome.check_name
                    for outcome in gate.outcomes
                    if not outcome.passed and outcome.severity == "reject"
                )
                print(f"[REJECTED] {preview['period']}: {reject_reasons}", file=sys.stderr)
                continue

            preview["signal_id"] = signal.id
            preview["action"] = "created" if created else "updated"

            _print_preview(preview, prefix="[INGESTED]")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
