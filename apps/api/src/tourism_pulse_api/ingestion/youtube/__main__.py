"""Reproducible YouTube search-interest ingestion command.

    python -m tourism_pulse_api.ingestion.youtube --place-id 61 --query "Budapest travel guide"
    python -m tourism_pulse_api.ingestion.youtube --place-id 61 \
        --query "Budapest travel guide" --dry-run

Requires an API key: set YOUTUBE_API_KEY in .env (enable the YouTube Data
API v3 at https://console.cloud.google.com/), or pass --api-key explicitly.

Like weather/events/OSM, this is a live source with no hardcoded place
list - the search query is supplied explicitly per run, not looked up
from a table baked into production code.

Running again never creates a duplicate signal: it overwrites the
place's single current search_interest value in place, keyed on
(place_id, signal_type, source) - see service.py's docstring for why.
"""

import argparse
import sys

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.ingestion.youtube.client import (
    DEFAULT_MAX_RESULTS,
    build_public_search_source_url,
    fetch_search_results,
)
from tourism_pulse_api.ingestion.youtube.parser import (
    YOUTUBE_SOURCE_NAME,
    parse_youtube_search,
)
from tourism_pulse_api.ingestion.youtube.service import (
    build_category_mentions_preview,
    build_preview,
    persist_videos,
    upsert_category_mentions_signals,
    upsert_search_interest_signal,
)
from tourism_pulse_api.settings import settings


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.youtube",
        description="Ingest YouTube search-interest counts as a demand signal for a place.",
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
        help='Search query, e.g. "Budapest travel guide".',
    )
    parser.add_argument(
        "--region-code",
        type=str,
        default=None,
        help="Optional ISO 3166-1 alpha-2 region code to bias results (e.g. HU).",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help=f"Sample size for titles/preview (default: {DEFAULT_MAX_RESULTS}).",
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
        help="Override YOUTUBE_API_KEY from the environment/.env.",
    )
    parser.add_argument(
        "--json-path",
        type=str,
        default=None,
        help="Read a local YouTube JSON response instead of fetching (e.g. for testing).",
    )
    return parser


def _load_response_text(
    *,
    api_key: str | None,
    query: str,
    region_code: str | None,
    max_results: int,
    json_path: str | None,
) -> str:
    if json_path is not None:
        with open(json_path, encoding="utf-8") as handle:
            return handle.read()

    if not api_key:
        raise ValueError(
            "No YouTube API key configured. Set YOUTUBE_API_KEY in .env or "
            "pass --api-key."
        )

    return fetch_search_results(
        api_key=api_key,
        query=query,
        region_code=region_code,
        max_results=max_results,
    )


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    api_key = args.api_key or settings.youtube_api_key

    try:
        text = _load_response_text(
            api_key=api_key,
            query=args.query,
            region_code=args.region_code,
            max_results=args.max_results,
            json_path=args.json_path,
        )
    except (OSError, ValueError) as exc:
        print(f"Failed to read YouTube data: {exc}", file=sys.stderr)
        return 1

    try:
        observation = parse_youtube_search(text, query=args.query)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    preview = build_preview(observation).as_dict()
    source_url = build_public_search_source_url(
        query=args.query,
        region_code=args.region_code,
        max_results=args.max_results,
    )

    if args.dry_run:
        print(f"[DRY RUN] {args.query!r}")
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
            source_name=YOUTUBE_SOURCE_NAME,
            dataset="youtube_search",
            raw_payload=text,
            content_type="application/json",
            place_id=args.place_id,
            source_url=source_url,
        )

        signal, gate = upsert_search_interest_signal(
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
            print(f"[REJECTED] {args.query!r}: {reject_reasons}", file=sys.stderr)
            return 1

        print(f"[INGESTED] {args.query!r}")
        for key, value in preview.items():
            if key == "query":
                continue
            print(f"    {key}: {value}")
        print(f"    signal_id: {signal.id}")

        videos = persist_videos(
            db,
            place_id=args.place_id,
            observation=observation,
            source_observation_id=source_observation.id,
        )
        print(f"    videos_persisted: {len(videos)}")

        category_results = upsert_category_mentions_signals(
            db,
            place_id=args.place_id,
            videos=videos,
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
