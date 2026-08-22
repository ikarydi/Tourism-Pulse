"""Reproducible GDELT news ingestion command.

    python -m tourism_pulse_api.ingestion.gdelt --place-id 61 \
        --query "Budapest tourism" --mode mentions
    python -m tourism_pulse_api.ingestion.gdelt --place-id 61 \
        --query "Budapest tourism" --mode sentiment
    python -m tourism_pulse_api.ingestion.gdelt --place-id 61 \
        --query "Budapest tourism" --dry-run

No API key needed - GDELT's DOC 2.0 API is fully open. `--mode` selects
which of the two independent signals to ingest (default: mentions); a
single run only ever makes one request, respecting GDELT's request-rate
courtesy notice (see client.py).

Running again never creates a duplicate signal: it overwrites the
place's single current value in place, keyed on
(place_id, signal_type, source) - see service.py's docstring for why.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.gdelt.client import (
    DEFAULT_MAX_RECORDS,
    DEFAULT_TIMESPAN,
    build_artlist_url,
    build_timelinetone_url,
    fetch_artlist,
    fetch_timelinetone,
)
from tourism_pulse_api.ingestion.gdelt.parser import (
    GDELT_SOURCE_NAME,
    parse_gdelt_artlist,
    parse_gdelt_timelinetone,
)
from tourism_pulse_api.ingestion.gdelt.service import (
    build_category_mentions_preview,
    build_mentions_preview,
    build_tone_preview,
    persist_articles,
    upsert_category_mentions_signals,
    upsert_news_mentions_signal,
    upsert_news_sentiment_signal,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.gdelt",
        description="Ingest GDELT news coverage volume/tone as a demand signal for a place.",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal to.",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help='Search query, e.g. "Budapest tourism".',
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="mentions",
        choices=["mentions", "sentiment"],
        help="Which signal to ingest (default: mentions).",
    )
    parser.add_argument(
        "--timespan",
        type=str,
        default=DEFAULT_TIMESPAN,
        help=f"GDELT timespan, e.g. 1d/1w/1m (default: {DEFAULT_TIMESPAN}).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=DEFAULT_MAX_RECORDS,
        help=f"Article cap for --mode mentions (default: {DEFAULT_MAX_RECORDS}, GDELT's own max).",
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
        help="Read a local GDELT JSON response instead of fetching (e.g. for testing).",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        if args.json_path is not None:
            with open(args.json_path, encoding="utf-8") as handle:
                text = handle.read()
        elif args.mode == "mentions":
            text = fetch_artlist(
                query=args.query, timespan=args.timespan, max_records=args.max_records
            )
        else:
            text = fetch_timelinetone(query=args.query, timespan=args.timespan)
    except OSError as exc:
        print(f"Failed to read GDELT data: {exc}", file=sys.stderr)
        return 1

    try:
        if args.mode == "mentions":
            observation = parse_gdelt_artlist(text, query=args.query)
            preview = build_mentions_preview(observation).as_dict()
        else:
            observation = parse_gdelt_timelinetone(text, query=args.query)
            preview = build_tone_preview(observation).as_dict()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    dataset = f"gdelt_doc_{'artlist' if args.mode == 'mentions' else 'timelinetone'}"
    # No API key involved - the real request URL and the publicly
    # storable one are identical for GDELT.
    source_url = (
        build_artlist_url(query=args.query, timespan=args.timespan, max_records=args.max_records)
        if args.mode == "mentions"
        else build_timelinetone_url(query=args.query, timespan=args.timespan)
    )

    if args.dry_run:
        print(f"[DRY RUN] {args.mode}: {args.query!r}")
        for key, value in preview.items():
            if key == "query":
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
            source_name=GDELT_SOURCE_NAME,
            dataset=dataset,
            raw_payload=text,
            content_type="application/json",
            place_id=args.place_id,
            source_url=source_url,
        )

        if args.mode == "mentions":
            signal, gate = upsert_news_mentions_signal(
                db,
                place_id=args.place_id,
                observation=observation,
                source_url=source_url,
                source_observation_id=source_observation.id,
            )
        else:
            signal, gate = upsert_news_sentiment_signal(
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
            print(f"[REJECTED] {args.mode}: {args.query!r}: {reject_reasons}", file=sys.stderr)
            return 1

        print(f"[INGESTED] {args.mode}: {args.query!r}")
        for key, value in preview.items():
            if key == "query":
                continue
            print(f"    {key}: {value}")
        print(f"    signal_id: {signal.id}")

        if args.mode == "mentions":
            articles = persist_articles(
                db,
                place_id=args.place_id,
                observation=observation,
                source_observation_id=source_observation.id,
            )
            print(f"    articles_persisted: {len(articles)}")

            category_results = upsert_category_mentions_signals(
                db,
                place_id=args.place_id,
                articles=articles,
                source_url=source_url,
                source_observation_id=source_observation.id,
                observed_at=observation.retrieved_at,
            )
            for category, (category_signal, category_gate) in category_results.items():
                if category_signal is None:
                    reject_reasons = "; ".join(
                        outcome.detail or outcome.check_name
                        for outcome in category_gate.outcomes
                        if not outcome.passed and outcome.severity == "reject"
                    )
                    print(f"    [REJECTED] {category.value}: {reject_reasons}", file=sys.stderr)
                    continue

                category_preview = build_category_mentions_preview(
                    category, int(category_signal.value)
                )
                print(f"    {category.value}:")
                for key, value in category_preview.as_dict().items():
                    if key in ("source", "category"):
                        continue
                    print(f"        {key}: {value}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
