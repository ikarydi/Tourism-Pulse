"""Fetch-once cache of monthly upload counts."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from tourism_pulse_api.ingestion.youtube_monthly.parser import parse_total_results

DEFAULT_CACHE_DIR = Path("data/youtube_monthly_cache")


class QuotaSpent(Exception):
    """The run's call budget is used up; the rest waits for the next run."""


def cache_path(cache_dir: Path, query: str, month: str) -> Path:
    key = hashlib.sha1(query.encode()).hexdigest()[:16]
    return cache_dir / key / f"{month}.json"


class MonthlyUploads:
    """Upload counts per (query, month), each fetched at most once.

    `fetch(query, month)` returns the raw API text. `budget` caps the
    number of network calls this run (the daily API quota)."""

    def __init__(self, fetch: Callable[[str, str], str], cache_dir: Path, budget: int):
        self._fetch = fetch
        self._cache_dir = cache_dir
        self.calls_left = budget

    def count(self, query: str, month: str) -> tuple[int, datetime]:
        path = cache_path(self._cache_dir, query, month)
        if path.exists():
            cached = json.loads(path.read_text())
            return int(cached["total_results"]), datetime.fromisoformat(cached["retrieved_at"])
        if self.calls_left <= 0:
            raise QuotaSpent
        self.calls_left -= 1
        total = parse_total_results(self._fetch(query, month))
        retrieved_at = datetime.now(UTC)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "query": query,
                    "month": month,
                    "total_results": total,
                    "retrieved_at": retrieved_at.isoformat(),
                }
            )
        )
        temporary.replace(path)
        return total, retrieved_at
