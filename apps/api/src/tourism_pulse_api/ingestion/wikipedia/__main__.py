"""Reproducible Wikipedia pageviews ingestion command.

    python -m tourism_pulse_api.ingestion.wikipedia --place-id 61 --article Budapest
    python -m tourism_pulse_api.ingestion.wikipedia --place-id 61 \
        --article Budapest --dry-run

No API key required - the Wikimedia Analytics API is fully public and
keyless (see the package docstring).

Like weather/events/OSM/YouTube, this is a live source with no hardcoded
place list - the article title is supplied explicitly per run, not
looked up from a table baked into production code.

Running again never creates a duplicate signal: it overwrites the
place's single current wikipedia_pageviews value in place, keyed on
(place_id, signal_type, source) - see service.py's docstring for why.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.ingestion.wikipedia.client import (
    DEFAULT_AGENT,
    DEFAULT_DAYS,
    DEFAULT_PROJECT,
    build_request_url,
    fetch_pageviews,
)
from tourism_pulse_api.ingestion.wikipedia.parser import (
    WIKIPEDIA_SOURCE_NAME,
    parse_wikipedia_pageviews,
)
from tourism_pulse_api.ingestion.wikipedia.service import (
    build_preview,
    upsert_wikipedia_pageviews_signal,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.wikipedia",
        description="Ingest Wikipedia pageviews as a demand signal for a place.",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal to.",
    )
    parser.add_argument(
        "--article",
        type=str,
        required=True,
        help='Wikipedia article title, e.g. "Budapest".',
    )
    parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT,
        help=f"Wikimedia project domain (default: {DEFAULT_PROJECT}).",
    )
    parser.add_argument(
        "--agent",
        type=str,
        default=DEFAULT_AGENT,
        choices=["user", "all-agents"],
        help=f"Traffic agent filter (default: {DEFAULT_AGENT}).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Trailing window size in days (default: {DEFAULT_DAYS}).",
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
        help="Read a local Wikipedia pageviews JSON response instead of fetching.",
    )
    return parser


def _load_response_text(
    *,
    article: str,
    project: str,
    agent: str,
    days: int,
    json_path: str | None,
) -> str:
    if json_path is not None:
        with open(json_path, encoding="utf-8") as handle:
            return handle.read()

    return fetch_pageviews(
        article=article,
        project=project,
        agent=agent,
        days=days,
    )


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        text = _load_response_text(
            article=args.article,
            project=args.project,
            agent=args.agent,
            days=args.days,
            json_path=args.json_path,
        )
    except OSError as exc:
        print(f"Failed to read Wikipedia data: {exc}", file=sys.stderr)
        return 1

    try:
        observation = parse_wikipedia_pageviews(
            text,
            article=args.article,
            project=args.project,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    preview = build_preview(observation).as_dict()
    source_url = build_request_url(
        article=args.article,
        project=args.project,
        agent=args.agent,
        days=args.days,
    )

    if args.dry_run:
        print(f"[DRY RUN] {args.article!r}")
        for key, value in preview.items():
            if key == "article":
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
            source_name=WIKIPEDIA_SOURCE_NAME,
            dataset="wikipedia_pageviews",
            raw_payload=text,
            content_type="application/json",
            place_id=args.place_id,
            source_url=source_url,
        )

        signal, gate = upsert_wikipedia_pageviews_signal(
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
            print(f"[REJECTED] {args.article!r}: {reject_reasons}", file=sys.stderr)
            return 1

        print(f"[INGESTED] {args.article!r}")
        for key, value in preview.items():
            if key == "article":
                continue
            print(f"    {key}: {value}")
        print(f"    signal_id: {signal.id}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
