"""Page a month's search to the end and aggregate it."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from tourism_pulse_api.ingestion.bluesky.parser import parse_search_page
from tourism_pulse_api.pulse.felt_pressure import felt_pressure_share

MAX_PAGES = 100  # 10,000 posts a place and month


@dataclass(frozen=True)
class MonthResult:
    posts: int
    felt_pressure_share: float | None
    languages: dict[str, int]


def month_result(
    fetch_page: Callable[[str | None], str], *, max_pages: int = MAX_PAGES
) -> MonthResult | None:
    """Aggregate one place-month. `fetch_page(cursor)` returns raw JSON.
    None when the page cap is hit before the search ends: an incomplete
    count is never stored."""
    texts: list[str] = []
    languages: Counter[str] = Counter()
    cursor: str | None = None
    for _ in range(max_pages):
        page = parse_search_page(fetch_page(cursor))
        texts.extend(page.texts)
        languages.update(page.languages)
        cursor = page.cursor
        if cursor is None or not page.texts:
            return MonthResult(len(texts), felt_pressure_share(texts), dict(languages))
    return None
