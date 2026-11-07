"""Load Bluesky monthly post counts, felt pressure and language mix.

    python -m tourism_pulse_api.ingestion.bluesky              # last complete month
    python -m tourism_pulse_api.ingestion.bluesky --months 6
    python -m tourism_pulse_api.ingestion.bluesky --dry-run

Needs BLUESKY_HANDLE and BLUESKY_APP_PASSWORD. Signals:
bluesky_posts_monthly (with a language breakdown) and
bluesky_felt_pressure_share (0-1), for countries and curated destinations.
"""

import argparse
import json
import sys
from datetime import date

from tourism_pulse_api.ingestion.bluesky.client import SEARCH_URL, create_session, search_page
from tourism_pulse_api.ingestion.bluesky.service import month_result
from tourism_pulse_api.ingestion.social_monthly import (
    MonthlyValue,
    complete_months,
    month_start,
    next_month,
)
from tourism_pulse_api.pulse.felt_pressure import LEXICON_VERSION
from tourism_pulse_api.settings import settings

SOURCE_NAME = "bluesky"
POSTS_SIGNAL = "bluesky_posts_monthly"
PRESSURE_SIGNAL = "bluesky_felt_pressure_share"


def _iso(month: str) -> str:
    return month_start(month).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_months(count: int, today: date) -> list[str]:
    year, number = today.year, today.month
    for _ in range(count):
        year, number = (year - 1, 12) if number == 1 else (year, number - 1)
    return complete_months(f"{year:04d}-{number:02d}", today)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.bluesky")
    parser.add_argument("--months", type=int, default=1, help="Complete months back.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from tourism_pulse_api.db.models import Place
    from tourism_pulse_api.db.session import SessionLocal
    from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
    from tourism_pulse_api.ingestion.social_monthly import (
        upsert_language_breakdowns,
        upsert_monthly_signals,
    )

    months = _last_months(args.months, date.today())
    db = SessionLocal()
    try:
        places = db.query(Place).filter(Place.place_type.in_(["country", "destination"])).all()
        db.commit()
        if args.dry_run:
            for place in places:
                print(f"[DRY RUN] {place.name!r}: {', '.join(months)}")
            return 0
        if not (settings.bluesky_handle and settings.bluesky_app_password):
            print("Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD.", file=sys.stderr)
            return 1
        token = create_session(
            handle=settings.bluesky_handle, app_password=settings.bluesky_app_password
        )
        values: list[MonthlyValue] = []
        archive: dict[str, dict[str, object]] = {}
        skipped: list[str] = []
        for place in places:
            for month in months:

                def fetch(cursor: str | None, query: str = place.name, m: str = month) -> str:
                    return search_page(
                        token=token,
                        query=query,
                        since=_iso(m),
                        until=_iso(next_month(m)),
                        cursor=cursor,
                    )

                result = month_result(fetch)
                if result is None:
                    skipped.append(f"{place.name} {month}")
                    continue
                values.append(MonthlyValue(place.id, POSTS_SIGNAL, month, result.posts, "posts"))
                if result.felt_pressure_share is not None:
                    values.append(
                        MonthlyValue(
                            place.id, PRESSURE_SIGNAL, month, result.felt_pressure_share, "share"
                        )
                    )
                upsert_language_breakdowns(
                    db,
                    place_id=place.id,
                    signal_type=POSTS_SIGNAL,
                    month=month,
                    counts=result.languages,
                    source=SOURCE_NAME,
                )
                archive[f"{place.name} {month}"] = {
                    "posts": result.posts,
                    "felt_pressure_share": result.felt_pressure_share,
                    "languages": result.languages,
                }
        if skipped:
            print(f"[SKIPPED] over the page cap: {', '.join(skipped)}", file=sys.stderr)
        # Only aggregates are archived: no post text or handles are kept.
        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset="bluesky_monthly",
            raw_payload=json.dumps(
                {"lexicon_version": LEXICON_VERSION, "place_months": archive}, ensure_ascii=False
            ),
            content_type="application/json",
            source_url=SEARCH_URL,
        )
        written = upsert_monthly_signals(
            db,
            values,
            source=SOURCE_NAME,
            source_url=SEARCH_URL,
            source_observation_id=observation.id,
        )
        db.commit()
        print(f"[INGESTED] {written} monthly values, {len(archive)} place-months")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
