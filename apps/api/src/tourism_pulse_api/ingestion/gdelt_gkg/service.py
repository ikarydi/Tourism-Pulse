"""Fetch GDELT daily files, cache per-day summaries, write monthly signals.

Per curated place and month this writes:

- signals `gdelt_attention_share` (articles mentioning the place per
  million articles), `gdelt_tourism_share` (tourism articles mentioning it
  per million), `gdelt_tourism_tone` and `gdelt_news_tone` (mean tone of
  its tourism coverage and of all its coverage), and
- signal_breakdowns `gdelt_tourism_articles` by topic, with key "all" for
  the month's total tourism articles, so a topic's share of coverage is
  topic / all.
"""

import hashlib
import http.client
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from calendar import monthrange
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, Signal, SignalBreakdown
from tourism_pulse_api.ingestion.eurostat.parser import eurostat_geo_code
from tourism_pulse_api.ingestion.gdelt_gkg.parser import (
    BUDAPEST_ADM1,
    FIPS,
    KSH_AREA_PREFIXES,
    KSH_AREA_TOWNS,
    Target,
    empty_counts,
    summarise_day,
)

SOURCE_NAME = "gdelt"
GKG_URL = "https://data.gdeltproject.org/gkg/{day}.gkg.csv.zip"
SOURCE_URL = "https://data.gdeltproject.org/gkg/"
USER_AGENT = "tourism-pulse-ingestion/1.0"
PER_MILLION = 1_000_000
BREAKDOWN_TYPE = "gdelt_tourism_articles"
# A month needs this many daily files before it is written, so a new month
# appears once its shares have settled; shares don't depend on month length.
MIN_DAYS = 10
# Mean tones are only written when this many articles back them.
MIN_TONE_ARTICLES = {"gdelt_tourism_tone": 5, "gdelt_news_tone": 20}
_BATCH_ROWS = 1000
# Bump when parser.py's matching or topic rules change, so cached days are
# recomputed instead of mixing old and new rules.
MATCHING_VERSION = "1"


def build_targets(db: Session) -> list[Target]:
    """Every curated place GDELT coverage can be counted for."""
    targets = []
    places = db.query(Place).filter(Place.place_type.in_(("country", "destination")))
    for place in places:
        if place.place_type == "country":
            fips = FIPS.get(place.nuts_code or "")
            if fips:
                targets.append(Target(place_id=place.id, fips=fips, country=True))
            continue
        country_code = place.destination.country_code if place.destination else None
        fips = FIPS.get(eurostat_geo_code(country_code)) if country_code else None
        if not fips:
            continue
        if fips == "HU" and place.name == "Budapest":
            targets.append(Target(place_id=place.id, fips=fips, adm1=BUDAPEST_ADM1))
        elif fips == "HU" and place.name in KSH_AREA_TOWNS:
            targets.append(
                Target(
                    place_id=place.id,
                    fips=fips,
                    towns=KSH_AREA_TOWNS[place.name],
                    prefixes=KSH_AREA_PREFIXES.get(place.name, ()),
                )
            )
        elif place.latitude is not None and place.longitude is not None:
            targets.append(
                Target(
                    place_id=place.id,
                    fips=fips,
                    latitude=place.latitude,
                    longitude=place.longitude,
                )
            )
    return sorted(targets, key=lambda target: target.place_id)


def targets_key(targets: list[Target]) -> str:
    """Identifies a target set, so a cached day made for other targets
    (or other matching rules) is recomputed rather than reused."""
    described = json.dumps([asdict(target) for target in targets], sort_keys=True, default=sorted)
    return hashlib.sha256((MATCHING_VERSION + described).encode()).hexdigest()[:16]


def download_day(day: date) -> str | None:
    """One day's GKG file as text, or None when GDELT has no file for it."""
    request = urllib.request.Request(
        GKG_URL.format(day=f"{day:%Y%m%d}"), headers={"User-Agent": USER_AGENT}
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None  # GDELT has occasional missing days
            if attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException, ConnectionError):
            # Includes connections dropped mid-file (IncompleteRead).
            if attempt == 4:
                raise
        time.sleep(2**attempt)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return archive.read(archive.namelist()[0]).decode("utf-8", errors="replace")


def fetch_day(day: date, targets: list[Target], cache_dir: Path) -> tuple[date, dict | None]:
    """The day's summary, from the cache when it was made for these targets."""
    key = targets_key(targets)
    cache = cache_dir / f"{day:%Y%m%d}.json"
    if cache.exists():
        cached = json.loads(cache.read_text())
        if cached.get("targets") == key:
            return day, cached["summary"]
    text = download_day(day)
    summary = None if text is None else summarise_day(text, targets)
    cache.write_text(json.dumps({"targets": key, "summary": summary}))
    return day, summary


def month_end(year: int, month: int) -> datetime:
    return datetime(year, month, monthrange(year, month)[1], tzinfo=UTC)


def aggregate_months(days: dict[date, dict | None]) -> dict[tuple[int, int], dict]:
    """(year, month) -> summed day summaries plus the count of days with a file."""
    months: dict[tuple[int, int], dict] = {}
    for day, summary in days.items():
        if summary is None:
            continue
        month = months.setdefault(
            (day.year, day.month),
            {"days": 0, "corpus": 0, "tourism": 0, "topics": {}, "places": {}},
        )
        month["days"] += 1
        month["corpus"] += summary["corpus"]
        month["tourism"] += summary["tourism"]
        for topic, count in summary["topics"].items():
            month["topics"][topic] = month["topics"].get(topic, 0) + count
        for place_id, counts in summary["places"].items():
            total = month["places"].setdefault(int(place_id), empty_counts())
            for field in ("mentions", "mention_tone", "tourism", "tourism_tone"):
                total[field] += counts[field]
            for topic, count in counts["topics"].items():
                total["topics"][topic] = total["topics"].get(topic, 0) + count
    return months


def monthly_values(
    months: dict[tuple[int, int], dict], place_ids: Iterable[int]
) -> tuple[list[dict], list[dict]]:
    """Signal rows and breakdown rows for every complete-enough month."""
    signals: list[dict] = []
    breakdowns: list[dict] = []
    for (year, month), totals in sorted(months.items()):
        if totals["days"] < MIN_DAYS or totals["corpus"] <= 0:
            continue
        observed_at = month_end(year, month)
        for place_id in place_ids:
            counts = totals["places"].get(place_id, empty_counts())
            values = {
                "gdelt_attention_share": (
                    counts["mentions"] / totals["corpus"] * PER_MILLION,
                    "per_million_articles",
                ),
                "gdelt_tourism_share": (
                    counts["tourism"] / totals["corpus"] * PER_MILLION,
                    "per_million_articles",
                ),
            }
            if counts["tourism"] >= MIN_TONE_ARTICLES["gdelt_tourism_tone"]:
                values["gdelt_tourism_tone"] = (counts["tourism_tone"] / counts["tourism"], "tone")
            if counts["mentions"] >= MIN_TONE_ARTICLES["gdelt_news_tone"]:
                values["gdelt_news_tone"] = (counts["mention_tone"] / counts["mentions"], "tone")
            for signal_type, (value, unit) in values.items():
                signals.append(
                    {
                        "place_id": place_id,
                        "signal_type": signal_type,
                        "value": round(value, 6),
                        "unit": unit,
                        "observed_at": observed_at,
                    }
                )
            if counts["tourism"] > 0:
                for key, value in {"all": counts["tourism"], **counts["topics"]}.items():
                    breakdowns.append(
                        {
                            "place_id": place_id,
                            "signal_type": BREAKDOWN_TYPE,
                            "observed_at": observed_at,
                            "dimension": "topic",
                            "key": key,
                            "value": value,
                            "source": SOURCE_NAME,
                        }
                    )
    return signals, breakdowns


def upsert(
    db: Session,
    signals: list[dict],
    breakdowns: list[dict],
    *,
    source_observation_id: int | None,
) -> None:
    for row in signals:
        row.update(
            source=SOURCE_NAME,
            source_url=SOURCE_URL,
            source_observation_id=source_observation_id,
        )
    for start in range(0, len(signals), _BATCH_ROWS):
        statement = insert(Signal).values(signals[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            constraint="uq_signals_place_type_observed_source",
            set_={
                "value": statement.excluded.value,
                "unit": statement.excluded.unit,
                "source_observation_id": statement.excluded.source_observation_id,
            },
        )
        db.execute(statement)
    for start in range(0, len(breakdowns), _BATCH_ROWS):
        statement = insert(SignalBreakdown).values(breakdowns[start : start + _BATCH_ROWS])
        statement = statement.on_conflict_do_update(
            constraint="uq_signal_breakdowns_place_type_observed_dimension_key",
            set_={"value": statement.excluded.value},
        )
        db.execute(statement)
