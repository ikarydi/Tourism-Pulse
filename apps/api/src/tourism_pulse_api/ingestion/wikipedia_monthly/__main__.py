"""Load monthly Wikipedia pageviews for countries and curated places.

python -m tourism_pulse_api.ingestion.wikipedia_monthly
python -m tourism_pulse_api.ingestion.wikipedia_monthly --dry-run

The total (`wikipedia_views_monthly`) is the English and German articles
(Hungarian too for KSH tourism areas), as used since the nowcast research.
Views per language edition - the market languages in articles.py plus the
place's own - go to signal_breakdowns under the same signal type, as a read
on which source markets are looking.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

from sqlalchemy.dialects.postgresql import insert

from tourism_pulse_api.db.models import Place, Signal, SignalBreakdown
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.ingestion.wikipedia_monthly.articles import (
    DESTINATION_TITLES,
    KSH_AREA_ARTICLES,
    LOCAL_LANGUAGES,
    MARKET_LANGUAGES,
    USER_AGENT,
    Article,
    resolve_titles,
)

SOURCE_NAME = "wikipedia"
SIGNAL_TYPE = "wikipedia_views_monthly"
PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "{language}.wikipedia/all-access/user/{title}/monthly/2015070100/{end}"
)


def _monthly_views(article: Article, end: str) -> dict[str, int]:
    url = PAGEVIEWS_URL.format(
        language=article.language,
        title=urllib.parse.quote(article.title.replace(" ", "_"), safe=""),
        end=end,
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                items = json.load(response)["items"]
            return {item["timestamp"][:6]: int(item["views"]) for item in items}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            if exc.code != 429 or attempt == 7:
                raise
            # Throttled: back off for up to two minutes before retrying.
            time.sleep(min(120, 5 * 2**attempt))
    return {}


def _country_code(place: Place) -> str | None:
    return place.destination.country_code if place.destination else None


def _articles_for(
    places: list[Place],
) -> tuple[dict[int, list[Article]], dict[int, list[Article]], list[str]]:
    """Per place: the articles summed into the total, the articles per
    language edition for the breakdown, and names with no usable article."""
    totals: dict[int, list[Article]] = {}
    editions: dict[int, list[Article]] = {}
    unresolved: list[str] = []
    to_resolve: dict[int, str] = {}
    for place in places:
        if place.name in KSH_AREA_ARTICLES:
            ksh = [
                Article(language, title)
                for language, titles in KSH_AREA_ARTICLES[place.name].items()
                for title in titles
            ]
            totals[place.id] = ksh
            editions[place.id] = ksh
        elif place.place_type == "destination":
            to_resolve[place.id] = DESTINATION_TITLES.get(place.name, place.name)
        else:
            to_resolve[place.id] = place.name
    resolved = resolve_titles(sorted(set(to_resolve.values())))
    by_id = {place.id: place for place in places}
    for place_id, name in to_resolve.items():
        titles = resolved.get(name)
        if titles is None:
            unresolved.append(by_id[place_id].name)
            continue
        totals[place_id] = [Article("en", titles["en"])] + (
            [Article("de", titles["de"])] if "de" in titles else []
        )
        local = LOCAL_LANGUAGES.get(_country_code(by_id[place_id]) or "")
        languages = list(MARKET_LANGUAGES)
        if local and local not in languages:
            languages.append(local)
        editions[place_id] = [
            Article(language, titles[language]) for language in languages if language in titles
        ]
    return totals, editions, unresolved


def _month_end(month: str) -> datetime:
    year, number = int(month[:4]), int(month[4:6])
    next_month = date(year + (number == 12), number % 12 + 1, 1)
    last_day = date.fromordinal(next_month.toordinal() - 1)
    return datetime(last_day.year, last_day.month, last_day.day, tzinfo=UTC)


def _summed(
    items: list[Article], fetched: dict[Article, dict[str, int]], current_month: str
) -> dict[str, int]:
    """month -> views over `items`, for months every item reports and
    never the current, incomplete month."""
    months: dict[str, list[int]] = defaultdict(list)
    for article in items:
        for month, views in fetched.get(article, {}).items():
            months[month].append(views)
    return {
        month: sum(values)
        for month, values in months.items()
        if len(values) == len(items) and month < current_month
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.wikipedia_monthly")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    today = date.today()
    end = f"{today:%Y%m}0100"  # exclusive of the current, incomplete month
    current_month = f"{today:%Y%m}"

    db = SessionLocal()
    try:
        places = db.query(Place).filter(Place.place_type.in_(["country", "destination"])).all()
        totals, editions, unresolved = _articles_for(places)
        # End the read transaction before the long fetch: an open one holds
        # locks that block migrations for the whole run.
        db.commit()
        if unresolved:
            print(
                f"[SKIPPED] no unambiguous article: {', '.join(sorted(unresolved))}",
                file=sys.stderr,
            )
        if args.dry_run:
            for place in places:
                if place.id in totals:
                    titles = ", ".join(f"{a.language}:{a.title}" for a in totals[place.id])
                    languages = ", ".join(a.language for a in editions.get(place.id, []))
                    print(f"[DRY RUN] {place.name}: {titles} | editions: {languages}")
            return 0

        unique = sorted(
            {a for items in [*totals.values(), *editions.values()] for a in items}, key=str
        )

        def fetch(article: Article) -> tuple[Article, dict[str, int]]:
            time.sleep(0.5)  # about four requests a second in all: polite to Wikimedia
            return article, _monthly_views(article, end)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fetched: dict[Article, dict[str, int]] = dict(pool.map(fetch, unique))

        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset="wikipedia_views_monthly",
            raw_payload=json.dumps(
                {f"{a.language}:{a.title}": views for a, views in fetched.items()},
                ensure_ascii=False,
            ),
            content_type="application/json",
            source_url=PAGEVIEWS_URL,
        )

        rows = [
            {
                "place_id": place_id,
                "signal_type": SIGNAL_TYPE,
                "value": views,
                "unit": "views",
                "observed_at": _month_end(month),
                "source": SOURCE_NAME,
                "source_url": "https://wikimedia.org/api/rest_v1/metrics/pageviews",
                "source_observation_id": observation.id,
            }
            for place_id, items in totals.items()
            for month, views in _summed(items, fetched, current_month).items()
        ]
        breakdowns = []
        for place_id, items in editions.items():
            by_language: dict[str, list[Article]] = defaultdict(list)
            for article in items:
                by_language[article.language].append(article)
            for language, language_items in by_language.items():
                for month, views in _summed(language_items, fetched, current_month).items():
                    breakdowns.append(
                        {
                            "place_id": place_id,
                            "signal_type": SIGNAL_TYPE,
                            "observed_at": _month_end(month),
                            "dimension": "language",
                            "key": language,
                            "value": views,
                            "source": SOURCE_NAME,
                        }
                    )
        for start in range(0, len(rows), 1000):
            statement = insert(Signal).values(rows[start : start + 1000])
            statement = statement.on_conflict_do_update(
                constraint="uq_signals_place_type_observed_source",
                set_={
                    "value": statement.excluded.value,
                    "source_observation_id": statement.excluded.source_observation_id,
                },
            )
            db.execute(statement)
        for start in range(0, len(breakdowns), 1000):
            statement = insert(SignalBreakdown).values(breakdowns[start : start + 1000])
            statement = statement.on_conflict_do_update(
                constraint="uq_signal_breakdowns_place_type_observed_dimension_key",
                set_={"value": statement.excluded.value},
            )
            db.execute(statement)
        db.commit()
        print(f"[INGESTED] {len(rows)} monthly values for {len(totals)} places")
        print(f"    and {len(breakdowns)} language values, from {len(fetched)} articles")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
