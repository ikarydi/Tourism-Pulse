"""Load monthly Wikipedia pageviews for countries and curated places.

python -m tourism_pulse_api.ingestion.wikipedia_monthly
python -m tourism_pulse_api.ingestion.wikipedia_monthly --dry-run
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, date, datetime

from sqlalchemy.dialects.postgresql import insert

from tourism_pulse_api.db.models import Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.ingestion.wikipedia_monthly.articles import (
    DESTINATION_TITLES,
    KSH_AREA_ARTICLES,
    USER_AGENT,
    Article,
    resolve_en_titles,
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
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                items = json.load(response)["items"]
            return {item["timestamp"][:6]: int(item["views"]) for item in items}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            if exc.code != 429 or attempt == 5:
                raise
            time.sleep(2**attempt * 2)
    return {}


def _articles_for(places: list[Place]) -> tuple[dict[int, list[Article]], list[str]]:
    articles: dict[int, list[Article]] = {}
    unresolved: list[str] = []
    to_resolve: dict[int, str] = {}
    for place in places:
        if place.name in KSH_AREA_ARTICLES:
            articles[place.id] = [
                Article(language, title)
                for language, titles in KSH_AREA_ARTICLES[place.name].items()
                for title in titles
            ]
        elif place.place_type == "destination":
            to_resolve[place.id] = DESTINATION_TITLES.get(place.name, place.name)
        else:
            to_resolve[place.id] = place.name
    resolved = resolve_en_titles(sorted(set(to_resolve.values())))
    names = {place.id: place.name for place in places}
    for place_id, name in to_resolve.items():
        titles = resolved.get(name)
        if titles is None:
            unresolved.append(names[place_id])
            continue
        english, german = titles
        articles[place_id] = [Article("en", english)] + ([Article("de", german)] if german else [])
    return articles, unresolved


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
        articles, unresolved = _articles_for(places)
        if unresolved:
            print(
                f"[SKIPPED] no unambiguous article: {', '.join(sorted(unresolved))}",
                file=sys.stderr,
            )
        if args.dry_run:
            for place in places:
                if place.id in articles:
                    titles = ", ".join(f"{a.language}:{a.title}" for a in articles[place.id])
                    print(f"[DRY RUN] {place.name}: {titles}")
            return 0

        fetched: dict[Article, dict[str, int]] = {}
        for article in sorted({a for items in articles.values() for a in items}, key=str):
            fetched[article] = _monthly_views(article, end)
            time.sleep(0.5)  # stay polite to the Wikimedia REST API

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

        rows = []
        for place_id, items in articles.items():
            months: dict[str, list[int]] = defaultdict(list)
            for article in items:
                for month, views in fetched.get(article, {}).items():
                    months[month].append(views)
            for month, values in months.items():
                # Every article must report the month, and never the current one.
                if len(values) != len(items) or month >= current_month:
                    continue
                year, number = int(month[:4]), int(month[4:6])
                next_month = date(year + (number == 12), number % 12 + 1, 1)
                last_day = date.fromordinal(next_month.toordinal() - 1)
                rows.append(
                    {
                        "place_id": place_id,
                        "signal_type": SIGNAL_TYPE,
                        "value": sum(values),
                        "unit": "views",
                        "observed_at": datetime(
                            last_day.year, last_day.month, last_day.day, tzinfo=UTC
                        ),
                        "source": SOURCE_NAME,
                        "source_url": "https://wikimedia.org/api/rest_v1/metrics/pageviews",
                        "source_observation_id": observation.id,
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
        db.commit()
        print(f"[INGESTED] {len(rows)} monthly values for {len(articles)} places")
        print(f"    from {len(fetched)} articles")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
