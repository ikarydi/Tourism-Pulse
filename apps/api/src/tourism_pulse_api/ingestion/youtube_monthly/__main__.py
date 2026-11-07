"""Load monthly YouTube upload counts.

Countries (Gate 4 data, to CSV; no database needed):
    python -m tourism_pulse_api.ingestion.youtube_monthly --countries \
        --export research/gate4/data/youtube_uploads.csv

Curated places and countries in the database (signal youtube_uploads_monthly):
    python -m tourism_pulse_api.ingestion.youtube_monthly --start 2024-01

Each month is fetched once and cached under --cache-dir; --max-calls caps
this run's API calls (100 quota units each). A run that hits the cap
stops and the next run carries on from the cache.
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from tourism_pulse_api.ingestion.social_monthly import MonthlyValue, complete_months
from tourism_pulse_api.ingestion.youtube_monthly.client import (
    SEARCH_URL,
    fetch_month,
)
from tourism_pulse_api.ingestion.youtube_monthly.countries import COUNTRY_NAMES
from tourism_pulse_api.ingestion.youtube_monthly.service import (
    DEFAULT_CACHE_DIR,
    MonthlyUploads,
    QuotaSpent,
)
from tourism_pulse_api.settings import settings

SOURCE_NAME = "youtube"
SIGNAL_TYPE = "youtube_uploads_monthly"
DEFAULT_MAX_CALLS = 95  # a day's default quota, with a little to spare


def query_for(name: str) -> str:
    return f"{name} travel"


def _export_countries(uploads: MonthlyUploads, months: list[str], path: Path) -> int:
    rows: list[dict[str, object]] = []
    stopped = False
    for month in sorted(months, reverse=True):
        for geo, name in COUNTRY_NAMES.items():
            try:
                total, retrieved_at = uploads.count(query_for(name), month)
            except QuotaSpent:
                stopped = True
                break
            rows.append(
                {
                    "geo": geo,
                    "month": month,
                    "uploads": total,
                    "retrieved_at": retrieved_at.isoformat(timespec="seconds"),
                }
            )
        if stopped:
            break
    rows.sort(key=lambda row: (str(row["geo"]), str(row["month"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["geo", "month", "uploads", "retrieved_at"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[EXPORTED] {len(rows)} country-months to {path}")
    if stopped:
        print("[PAUSED] call budget spent; run again to continue", file=sys.stderr)
        return 2
    return 0


def _load_places(uploads: MonthlyUploads, months: list[str], dry_run: bool) -> int:
    from tourism_pulse_api.db.models import Place
    from tourism_pulse_api.db.session import SessionLocal
    from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
    from tourism_pulse_api.ingestion.social_monthly import upsert_monthly_signals

    db = SessionLocal()
    try:
        places = db.query(Place).filter(Place.place_type.in_(["country", "destination"])).all()
        db.commit()
        if dry_run:
            for place in places:
                print(f"[DRY RUN] {place.name}: {query_for(place.name)!r} x {len(months)} months")
            return 0
        values: list[MonthlyValue] = []
        raw: dict[str, dict[str, int]] = {}
        stopped = False
        # Newest month first, countries before destinations: the latest
        # month is frozen for every place before older months are backfilled.
        places.sort(key=lambda p: (p.place_type != "country", p.name))
        for month in sorted(months, reverse=True):
            for place in places:
                query = query_for(place.name)
                try:
                    total, _ = uploads.count(query, month)
                except QuotaSpent:
                    stopped = True
                    break
                raw.setdefault(query, {})[month] = total
                values.append(MonthlyValue(place.id, SIGNAL_TYPE, month, total, "videos"))
            if stopped:
                break
        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset=SIGNAL_TYPE,
            raw_payload=json.dumps(raw, ensure_ascii=False),
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
        print(f"[INGESTED] {written} monthly upload counts")
        if stopped:
            print("[PAUSED] call budget spent; run again to continue", file=sys.stderr)
    finally:
        db.close()
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.youtube_monthly")
    parser.add_argument("--countries", action="store_true", help="Gate 4 country series.")
    parser.add_argument("--export", type=Path, help="CSV path (with --countries).")
    parser.add_argument("--start", default="2016-01", help="First month, YYYY-MM.")
    parser.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    api_key = args.api_key or settings.youtube_api_key
    if not api_key and not args.dry_run:
        print("No YouTube API key: set YOUTUBE_API_KEY or pass --api-key.", file=sys.stderr)
        return 1

    def fetch(query: str, month: str) -> str:
        return fetch_month(api_key=api_key or "", query=query, month=month)

    uploads = MonthlyUploads(fetch, args.cache_dir, args.max_calls)
    months = complete_months(args.start, date.today())

    if args.countries:
        if args.export is None:
            print("--countries needs --export PATH.", file=sys.stderr)
            return 1
        return _export_countries(uploads, months, args.export)
    return _load_places(uploads, months, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(run())
