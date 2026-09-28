"""Build the GDELT inputs from GDELT's daily Global Knowledge Graph files.

See PREREGISTRATION.md, Amendment 1. Each daily file
(data.gdeltproject.org/gkg/YYYYMMDD.gkg.csv.zip, ~20-30 MB) lists article
records with THEMES, LOCATIONS (FIPS country codes) and TONE. Per day and
country this keeps only three numbers - tourism article count, their
tone-weighted sum, and the day's total article count - so ~90 GB of files
stream through without being stored.

The static file server does not throttle the way the DOC API does, and
per-day results are cached, so an interrupted run resumes where it
stopped.

Run: python -m research.nowcast.gkg   (from the repo root)
Writes research/nowcast/data/gdelt.csv in the schema backtest.py reads.

    python -m research.nowcast.gkg --phase 2

adds the pre-COVID span (PREREGISTRATION.md, phase 2) and writes
data/gdelt_full.csv instead; cached 2022+ days are reused.
"""

import argparse
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd

from research.nowcast.data import DATA_DIR, USER_AGENT

GKG_URL = "https://data.gdeltproject.org/gkg/{day}.gkg.csv.zip"
CACHE_DIR = DATA_DIR / "gkg_cache"
# PREREGISTRATION.md Amendment 2: GDELT history starts 2022-01. Earlier
# months would only feed samples the COVID exclusion drops anyway, except
# 2018-2020 pre-COVID training history, traded away for a ~1 h faster build.
START = date(2022, 1, 1)
# Phase 2 adds the pre-COVID span. 2020-03 .. 2021-12 stays skipped: it
# only feeds samples the COVID exclusion drops.
PRE_COVID_START = date(2017, 1, 1)
PRE_COVID_END = date(2020, 2, 29)
WORKERS = 14

TOURISM_THEMES = frozenset(
    {"TOURISM", "WB_825_TOURISM", "TAX_FNCACT_TOURIST", "TAX_FNCACT_TOURISTS"}
)

# Eurostat geo code -> FIPS 10-4 country code used in GKG LOCATIONS.
FIPS: dict[str, str] = {
    "AT": "AU", "BE": "BE", "BG": "BU", "CY": "CY", "CZ": "EZ", "DE": "GM",
    "DK": "DA", "EE": "EN", "EL": "GR", "ES": "SP", "FI": "FI", "FR": "FR",
    "HR": "HR", "HU": "HU", "IE": "EI", "IT": "IT", "LT": "LH", "LU": "LU",
    "LV": "LG", "MT": "MT", "NL": "NL", "PL": "PL", "PT": "PO", "RO": "RO",
    "SE": "SW", "SI": "SI", "SK": "LO", "NO": "NO", "IS": "IC", "CH": "SZ",
}  # fmt: skip
GEO_BY_FIPS = {fips: geo for geo, fips in FIPS.items()}


def summarise_day(text: str) -> dict:
    """Per-country tourism articles and tone for one GKG daily file."""
    corpus = 0
    articles = dict.fromkeys(FIPS, 0)
    tone_x_articles = dict.fromkeys(FIPS, 0.0)

    lines = text.splitlines()
    for line in lines[1:]:  # first line is the header
        # Cheap pre-filter: only ~2% of records mention tourists at all.
        if "TOURIS" not in line:
            numarts = line.split("\t", 2)[1] if "\t" in line else ""
            corpus += int(numarts) if numarts.isdigit() else 0
            continue

        fields = line.split("\t")
        if len(fields) < 8 or not fields[1].isdigit():
            continue
        numarts = int(fields[1])
        corpus += numarts

        if TOURISM_THEMES.isdisjoint(fields[3].split(";")):
            continue

        countries = {
            location.split("#")[2] for location in fields[4].split(";") if location.count("#") >= 2
        }
        tone = float(fields[7].split(",")[0]) if fields[7] else 0.0
        for fips in countries & GEO_BY_FIPS.keys():
            geo = GEO_BY_FIPS[fips]
            articles[geo] += numarts
            tone_x_articles[geo] += tone * numarts

    return {"corpus": corpus, "articles": articles, "tone_x_articles": tone_x_articles}


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
                # GDELT has occasional missing days.
                return None
            if attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(2**attempt)

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return archive.read(archive.namelist()[0]).decode("utf-8", errors="replace")


def fetch_day(day: date) -> tuple[date, dict | None]:
    cache = CACHE_DIR / f"{day:%Y%m%d}.json"
    if cache.exists():
        return day, json.loads(cache.read_text())

    text = download_day(day)
    summary = None if text is None else summarise_day(text)
    cache.write_text(json.dumps(summary))
    return day, summary


def build_monthly(days: dict[date, dict | None]) -> pd.DataFrame:
    rows = []
    for day, summary in days.items():
        if summary is None:
            continue
        for geo in FIPS:
            rows.append(
                {
                    "geo": geo,
                    "month": f"{day:%Y-%m}",
                    "articles": summary["articles"][geo],
                    "corpus": summary["corpus"],
                    "tone_x_articles": summary["tone_x_articles"][geo],
                    "days": 1,
                }
            )
    daily = pd.DataFrame(rows)
    monthly = daily.groupby(["geo", "month"], as_index=False)[
        ["articles", "corpus", "tone_x_articles", "days"]
    ].sum()
    monthly["tone"] = monthly["tone_x_articles"] / monthly["articles"].where(
        monthly["articles"] > 0
    )
    return monthly.drop(columns="tone_x_articles").sort_values(["geo", "month"])


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("1", "2"), default="1")
    args = parser.parse_args()

    def span(first: date, last: date) -> list[date]:
        return [first + timedelta(days=i) for i in range((last - first).days + 1)]

    # Yesterday is the last complete daily file.
    all_days = span(START, date.today() - timedelta(days=1))
    output, missing_file = "gdelt.csv", "gdelt_missing_days.txt"
    if args.phase == "2":
        all_days = span(PRE_COVID_START, PRE_COVID_END) + all_days
        output, missing_file = "gdelt_full.csv", "gdelt_full_missing_days.txt"

    results: dict[date, dict | None] = {}
    started = time.time()
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(fetch_day, day) for day in all_days]
        for done, future in enumerate(as_completed(futures), start=1):
            day, summary = future.result()
            results[day] = summary
            if done % 100 == 0 or done == len(futures):
                elapsed = time.time() - started
                print(f"{done}/{len(futures)} days, {elapsed / 60:.1f} min", flush=True)

    missing = sorted(day for day, summary in results.items() if summary is None)
    monthly = build_monthly(results)
    monthly.to_csv(DATA_DIR / output, index=False)
    print(
        f"{output}: {len(monthly)} rows, {monthly['month'].min()}..{monthly['month'].max()}; "
        f"{len(missing)} missing days"
    )
    if missing:
        (DATA_DIR / missing_file).write_text("\n".join(f"{day:%Y-%m-%d}" for day in missing) + "\n")


if __name__ == "__main__":
    main()
