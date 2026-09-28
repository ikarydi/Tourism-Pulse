"""Fetch the regional study's KSH and Wikipedia inputs as tidy CSVs.

See PREREGISTRATION_REGIONAL.md. KSH is read with the API's own KSH
adapter (client + parser), so the backtest and the product share one
parsing of STADAT 27.2.1.19.

Run: python -m research.nowcast.regional_data   (from the repo root)
Writes research/nowcast/data/{ksh_areas,pageviews_regional}.csv.
"""

import json
import time
import urllib.parse

import pandas as pd
from tourism_pulse_api.ingestion.ksh.client import fetch_ksh_csv
from tourism_pulse_api.ingestion.ksh.parser import KSH_CSV_URL, SUPPORTED_REGIONS, parse_ksh_csv

from research.nowcast.data import DATA_DIR, PAGEVIEWS_URL, _get_json

# Area -> {language: [article titles]}; titles checked to be real articles,
# not disambiguation pages (see the pre-registration).
ARTICLES: dict[str, dict[str, list[str]]] = {
    "budapest": {"hu": ["Budapest"], "en": ["Budapest"], "de": ["Budapest"]},
    "balaton": {"hu": ["Balaton"], "en": ["Lake_Balaton"], "de": ["Balaton"]},
    "greater_budapest": {"hu": ["Szentendre"], "en": ["Szentendre"], "de": ["Szentendre"]},
    "buk_sarvar": {"hu": ["Bük", "Sárvár"], "en": ["Bük", "Sárvár"], "de": ["Bük", "Sárvár"]},
    "debrecen": {
        "hu": ["Debrecen", "Hajdúszoboszló"],
        "en": ["Debrecen", "Hajdúszoboszló"],
        "de": ["Debrecen", "Hajdúszoboszló"],
    },
    "gyor_pannonhalma": {
        "hu": ["Győr", "Pannonhalma"],
        "en": ["Győr", "Pannonhalma"],
        "de": ["Győr", "Pannonhalma"],
    },
    "gyula": {"hu": ["Gyula_(Magyarország)"], "en": ["Gyula,_Hungary"], "de": ["Gyula"]},
    "eger": {"hu": ["Eger"], "en": ["Eger"], "de": ["Eger_(Ungarn)"]},
    "pecs": {"hu": ["Pécs"], "en": ["Pécs"], "de": ["Pécs"]},
    "sopron": {"hu": ["Sopron"], "en": ["Sopron"], "de": ["Sopron"]},
    "szeged": {"hu": ["Szeged"], "en": ["Szeged"], "de": ["Szeged"]},
    "tokaj_nyiregyhaza": {
        "hu": ["Tokaj", "Nyíregyháza"],
        "en": ["Tokaj", "Nyíregyháza"],
        "de": ["Tokaj", "Nyíregyháza"],
    },
}


def fetch_ksh_areas() -> pd.DataFrame:
    observations = parse_ksh_csv(fetch_ksh_csv(KSH_CSV_URL), regions=list(SUPPORTED_REGIONS))
    return pd.DataFrame(
        [
            {
                "area": observation.region,
                "month": observation.period,
                "nights": float(observation.total_nights),
            }
            for observation in observations
        ]
    ).sort_values(["area", "month"])


def fetch_pageviews(end: str) -> pd.DataFrame:
    cache_dir = DATA_DIR / "pageviews_regional_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for area, by_language in ARTICLES.items():
        for language, titles in by_language.items():
            for title in titles:
                cache = cache_dir / f"{area}_{language}_{title.replace('/', '_')}.json"
                if cache.exists():
                    items = json.loads(cache.read_text())
                else:
                    url = PAGEVIEWS_URL.format(
                        project=f"{language}.wikipedia",
                        article=urllib.parse.quote(title, safe=""),
                        end=end,
                    )
                    items = _get_json(url)["items"]
                    cache.write_text(json.dumps(items))
                    time.sleep(1.0)  # stay polite to the Wikimedia REST API
                rows += [
                    {
                        "area": area,
                        "series": f"{language}:{title}",
                        "month": f"{item['timestamp'][:4]}-{item['timestamp'][4:6]}",
                        "views": int(item["views"]),
                    }
                    for item in items
                ]
    return pd.DataFrame(rows).sort_values(["area", "series", "month"])


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ksh = fetch_ksh_areas()
    ksh.to_csv(DATA_DIR / "ksh_areas.csv", index=False)
    print(f"ksh_areas: {len(ksh)} rows, {ksh['month'].min()}..{ksh['month'].max()}")

    views = fetch_pageviews(pd.Timestamp.now(tz="UTC").strftime("%Y%m0100"))
    views.to_csv(DATA_DIR / "pageviews_regional.csv", index=False)
    counts = views.groupby("area")["series"].nunique()
    print(f"pageviews_regional: {len(views)} rows; series per area: {counts.to_dict()}")


if __name__ == "__main__":
    main()
