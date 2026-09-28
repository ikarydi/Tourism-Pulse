"""GDELT attention per Hungarian tourism area, from the daily GKG files.

See PREREGISTRATION_REGIONAL.md. Per day and area this keeps the number
of records (NUMARTS) whose LOCATIONS mention the area - any theme, since
tourism-tagged counts outside Budapest are ~0 - plus the day's total, so
the backtest can use mention share.

Run: python -m research.nowcast.gkg_regional   (from the repo root)
Writes research/nowcast/data/gdelt_regional.csv.
"""

import json
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta

import pandas as pd

from research.nowcast.data import DATA_DIR
from research.nowcast.gkg import START, WORKERS, download_day

CACHE_DIR = DATA_DIR / "gkg_regional_cache"

# Area -> accent-folded, lower-case first parts of GDELT location names.
# Budapest is matched by ADM1 code instead, Balaton also by prefix.
AREA_NAMES: dict[str, frozenset[str]] = {
    "balaton": frozenset({"siofok", "keszthely", "heviz", "tihany", "zamardi", "fonyod"}),
    "greater_budapest": frozenset({"szentendre", "visegrad", "godollo", "vac"}),
    "buk_sarvar": frozenset({"buk", "bukfurdo", "sarvar"}),
    "debrecen": frozenset({"debrecen", "hajduszoboszlo"}),
    "gyor_pannonhalma": frozenset({"gyor", "pannonhalma"}),
    "gyula": frozenset({"gyula"}),
    "eger": frozenset({"eger", "egerszalok"}),
    "pecs": frozenset({"pecs"}),
    "sopron": frozenset({"sopron"}),
    "szeged": frozenset({"szeged"}),
    "tokaj_nyiregyhaza": frozenset({"tokaj", "nyiregyhaza"}),
}
AREAS = ("budapest", *AREA_NAMES)
BUDAPEST_ADM1 = "HU05"


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip()


def areas_for_location(location: str) -> set[str]:
    parts = location.split("#")
    if len(parts) < 4 or parts[2] != "HU":
        return set()
    if parts[3] == BUDAPEST_ADM1:
        return {"budapest"}
    first = fold(parts[1].split(",")[0])
    if first.startswith("balaton") or first.startswith("lake balaton"):
        return {"balaton"}
    return {area for area, names in AREA_NAMES.items() if first in names}


def summarise_day(text: str) -> dict:
    corpus = 0
    articles = dict.fromkeys(AREAS, 0)
    for line in text.splitlines()[1:]:
        fields = line.split("\t", 5)
        if len(fields) < 5 or not fields[1].isdigit():
            continue
        numarts = int(fields[1])
        corpus += numarts
        # Cheap pre-filter: only records with a Hungarian location matter.
        if "#HU#" not in fields[4]:
            continue
        matched: set[str] = set()
        for location in fields[4].split(";"):
            matched |= areas_for_location(location)
        for area in matched:
            articles[area] += numarts
    return {"corpus": corpus, "articles": articles}


def fetch_day(day: date) -> tuple[date, dict | None]:
    cache = CACHE_DIR / f"{day:%Y%m%d}.json"
    if cache.exists():
        return day, json.loads(cache.read_text())
    text = download_day(day)
    summary = None if text is None else summarise_day(text)
    cache.write_text(json.dumps(summary))
    return day, summary


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    end = date.today() - timedelta(days=1)
    days = [START + timedelta(days=i) for i in range((end - START).days + 1)]

    results: dict[date, dict | None] = {}
    started = time.time()
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(fetch_day, day) for day in days]
        for done, future in enumerate(as_completed(futures), start=1):
            day, summary = future.result()
            results[day] = summary
            if done % 100 == 0 or done == len(futures):
                print(
                    f"{done}/{len(futures)} days, {(time.time() - started) / 60:.1f} min",
                    flush=True,
                )

    rows = [
        {
            "area": area,
            "month": f"{day:%Y-%m}",
            "articles": summary["articles"][area],
            "corpus": summary["corpus"],
            "days": 1,
        }
        for day, summary in results.items()
        if summary is not None
        for area in AREAS
    ]
    monthly = (
        pd.DataFrame(rows)
        .groupby(["area", "month"], as_index=False)[["articles", "corpus", "days"]]
        .sum()
        .sort_values(["area", "month"])
    )
    monthly.to_csv(DATA_DIR / "gdelt_regional.csv", index=False)
    missing = sum(summary is None for summary in results.values())
    print(f"gdelt_regional.csv: {len(monthly)} rows; {missing} missing days")


if __name__ == "__main__":
    main()
