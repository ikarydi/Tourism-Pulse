"""Airbnb ingestion command - SCAFFOLD ONLY.

    python -m tourism_pulse_api.ingestion.airbnb --place-id 61

Always fails with a clear explanation and exit code 1: Airbnb has no
public API (see client.py's module docstring). This command exists so
the CLI surface is consistent with every other adapter's
`python -m tourism_pulse_api.ingestion.<source>` entrypoint, and so it
fails clearly rather than with an import error if something ever calls
it (e.g. a scheduler misconfigured to run it too early).
"""

import argparse
import sys

from tourism_pulse_api.ingestion.airbnb.client import (
    SourceNotConfiguredError,
    fetch_listings,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.airbnb",
        description="Ingest listing/demand data from Airbnb for a place (not yet implemented).",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal(s) to.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested without writing to the database.",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        fetch_listings(place_id=args.place_id)
    except SourceNotConfiguredError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Unreachable while fetch_listings always raises - kept so this
    # command's shape matches every other adapter's __main__.py once a
    # real fetch exists.
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
