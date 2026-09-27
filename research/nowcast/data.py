"""Fetch and cache the backtest's two data sources as tidy CSVs.

- Eurostat tour_occ_nim: monthly nights spent, residents + non-residents,
  hotels/holiday/camping (I551-I553) - the same scope the API's Eurostat
  adapter ingests. This is the "official figure" the nowcast predicts.
- Wikimedia pageviews: monthly user (non-bot) views per article, available
  from 2015-07, i.e. fully backfillable. Per country: the English country
  article, the German country article (Germany is Europe's largest source
  market) and the English capital-city article.

- GDELT DOC 2.0: daily article counts ("<country> tourism", the same
  query shape the API's GDELT adapter uses) with GDELT's own daily corpus
  total, plus average tone. Explicit start/end datetimes reach back to
  2017-01, so it is backfillable too - a shorter history than Wikipedia.
  Counts are kept with the corpus total so the backtest can use article
  *share*, which is immune to GDELT's monitored-source count changing.

Run: python -m research.nowcast.data   (from the repo root)
Writes research/nowcast/data/{nights,pageviews,gdelt}.csv plus a retrieval stamp,
so a backtest run is reproducible from committed files without network.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"

EUROSTAT_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tour_occ_nim"
PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "{project}/all-access/user/{article}/monthly/2015070100/{end}"
)
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_START = "20170101000000"
# GDELT asks for at most one request every 5 seconds.
GDELT_SPACING_SECONDS = 6.0
USER_AGENT = "TourismPulseResearch/0.1 (nowcast backtest)"

# Plain English names for GDELT queries (multi-word official names would
# be AND-ed word by word and over-restrict the match).
GDELT_NAMES: dict[str, str] = {
    "AT": "Austria",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CY": "Cyprus",
    "CZ": "Czech",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "EL": "Greece",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MT": "Malta",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "NO": "Norway",
    "IS": "Iceland",
    "CH": "Switzerland",
}

# Eurostat geo code -> (English article, German article, English capital article)
COUNTRIES: dict[str, tuple[str, str, str]] = {
    "AT": ("Austria", "Österreich", "Vienna"),
    "BE": ("Belgium", "Belgien", "Brussels"),
    "BG": ("Bulgaria", "Bulgarien", "Sofia"),
    "CY": ("Cyprus", "Republik_Zypern", "Nicosia"),
    "CZ": ("Czech_Republic", "Tschechien", "Prague"),
    "DE": ("Germany", "Deutschland", "Berlin"),
    "DK": ("Denmark", "Dänemark", "Copenhagen"),
    "EE": ("Estonia", "Estland", "Tallinn"),
    "EL": ("Greece", "Griechenland", "Athens"),
    "ES": ("Spain", "Spanien", "Madrid"),
    "FI": ("Finland", "Finnland", "Helsinki"),
    "FR": ("France", "Frankreich", "Paris"),
    "HR": ("Croatia", "Kroatien", "Zagreb"),
    "HU": ("Hungary", "Ungarn", "Budapest"),
    "IE": ("Republic_of_Ireland", "Irland", "Dublin"),
    "IT": ("Italy", "Italien", "Rome"),
    "LT": ("Lithuania", "Litauen", "Vilnius"),
    "LU": ("Luxembourg", "Luxemburg", "Luxembourg_City"),
    "LV": ("Latvia", "Lettland", "Riga"),
    "MT": ("Malta", "Malta", "Valletta"),
    "NL": ("Netherlands", "Niederlande", "Amsterdam"),
    "PL": ("Poland", "Polen", "Warsaw"),
    "PT": ("Portugal", "Portugal", "Lisbon"),
    "RO": ("Romania", "Rumänien", "Bucharest"),
    "SE": ("Sweden", "Schweden", "Stockholm"),
    "SI": ("Slovenia", "Slowenien", "Ljubljana"),
    "SK": ("Slovakia", "Slowakei", "Bratislava"),
    "NO": ("Norway", "Norwegen", "Oslo"),
    "IS": ("Iceland", "Island", "Reykjavík"),
    "CH": ("Switzerland", "Schweiz", "Bern"),
}


def _get_json(url: str, *, attempts: int = 6) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Wikimedia answers bursts with 429; back off and retry.
            if exc.code != 429 or attempt == attempts - 1:
                raise
            time.sleep(2**attempt * 2)
    raise AssertionError("unreachable")


def fetch_nights() -> pd.DataFrame:
    params = {
        "format": "JSON",
        "lang": "EN",
        "unit": "NR",
        "c_resid": "TOTAL",
        "nace_r2": "I551-I553",
        "sinceTimePeriod": "2014-01",
    }
    query = urllib.parse.urlencode(params) + "".join(f"&geo={geo}" for geo in COUNTRIES)
    payload = _get_json(f"{EUROSTAT_URL}?{query}")

    ids = payload["id"]
    sizes = payload["size"]
    geo_index = payload["dimension"]["geo"]["category"]["index"]
    time_index = payload["dimension"]["time"]["category"]["index"]
    geo_by_pos = {pos: code for code, pos in geo_index.items()}
    time_by_pos = {pos: period for period, pos in time_index.items()}

    # JSON-stat flattens the cube row-major over `ids`; every dimension
    # other than geo/time is fixed to size 1 by the query, so the flat
    # index decomposes into (geo, time) alone.
    n_time = sizes[ids.index("time")]
    n_geo = sizes[ids.index("geo")]

    rows = []
    for flat, value in payload["value"].items():
        flat = int(flat)
        rows.append(
            {
                "geo": geo_by_pos[(flat // n_time) % n_geo],
                "month": time_by_pos[flat % n_time],
                "nights": float(value),
            }
        )

    frame = pd.DataFrame(rows)
    frame["month"] = pd.PeriodIndex(frame["month"], freq="M").astype(str)
    return frame.sort_values(["geo", "month"]).reset_index(drop=True)


def fetch_pageviews(end: str) -> pd.DataFrame:
    rows = []
    for geo, (en_country, de_country, en_capital) in COUNTRIES.items():
        for series, project, article in (
            ("en_country", "en.wikipedia", en_country),
            ("de_country", "de.wikipedia", de_country),
            ("en_capital", "en.wikipedia", en_capital),
        ):
            url = PAGEVIEWS_URL.format(
                project=project,
                article=urllib.parse.quote(article, safe=""),
                end=end,
            )
            cache = DATA_DIR / "pageviews_cache" / f"{geo}_{series}.json"
            if cache.exists():
                items = json.loads(cache.read_text())
            else:
                items = _get_json(url)["items"]
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(items))
                time.sleep(1.0)  # stay polite to the Wikimedia REST API
            for item in items:
                rows.append(
                    {
                        "geo": geo,
                        "series": series,
                        "month": f"{item['timestamp'][:4]}-{item['timestamp'][4:6]}",
                        "views": int(item["views"]),
                    }
                )
    return pd.DataFrame(rows).sort_values(["geo", "series", "month"]).reset_index(drop=True)


def _get_gdelt(params: dict[str, str], *, attempts: int = 8) -> dict:
    url = f"{GDELT_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                raise
            body = ""
        # Throttling arrives either as HTTP 429 or as HTTP 200 with a
        # plain-text notice instead of JSON.
        if body.lstrip().startswith("{"):
            return json.loads(body)
        time.sleep(GDELT_SPACING_SECONDS * (attempt + 2))
    raise RuntimeError(f"GDELT kept throttling: {params['query']!r}")


def fetch_gdelt(end: str) -> pd.DataFrame:
    frames = []
    for geo, name in GDELT_NAMES.items():
        for mode in ("timelinevolraw", "timelinetone"):
            cache = DATA_DIR / "gdelt_cache" / f"{geo}_{mode}.json"
            if cache.exists():
                payload = json.loads(cache.read_text())
            else:
                payload = _get_gdelt(
                    {
                        "query": f"{name} tourism",
                        "mode": mode,
                        "format": "json",
                        "startdatetime": GDELT_START,
                        "enddatetime": end,
                        "timelinesmooth": "0",
                    }
                )
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(payload))
                time.sleep(GDELT_SPACING_SECONDS)

            points = payload["timeline"][0]["data"] if payload.get("timeline") else []
            daily = pd.DataFrame(points)
            if daily.empty:
                continue
            daily["day"] = pd.to_datetime(daily["date"].str[:8], format="%Y%m%d")
            daily["geo"] = geo
            if mode == "timelinevolraw":
                daily = daily.rename(columns={"value": "articles", "norm": "corpus"})
                frames.append(daily[["geo", "day", "articles", "corpus"]])
            else:
                daily = daily.rename(columns={"value": "tone"})
                frames.append(daily[["geo", "day", "tone"]])

    volume = pd.concat([f for f in frames if "articles" in f.columns])
    tone = pd.concat([f for f in frames if "tone" in f.columns])
    daily = volume.merge(tone, on=["geo", "day"], how="left")
    daily["month"] = daily["day"].dt.to_period("M").astype(str)
    # Monthly tone is the article-weighted mean of daily tone.
    daily["tone_x_articles"] = daily["tone"].fillna(0.0) * daily["articles"]
    monthly = daily.groupby(["geo", "month"], as_index=False)[
        ["articles", "corpus", "tone_x_articles"]
    ].sum()
    monthly["tone"] = monthly["tone_x_articles"] / monthly["articles"].where(
        monthly["articles"] > 0
    )
    return monthly.drop(columns="tone_x_articles").sort_values(["geo", "month"])


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC)
    end = retrieved_at.strftime("%Y%m0100")

    nights = fetch_nights()
    nights.to_csv(DATA_DIR / "nights.csv", index=False)

    pageviews = fetch_pageviews(end)
    pageviews.to_csv(DATA_DIR / "pageviews.csv", index=False)

    gdelt = fetch_gdelt(retrieved_at.strftime("%Y%m%d000000"))
    gdelt.to_csv(DATA_DIR / "gdelt.csv", index=False)

    (DATA_DIR / "RETRIEVED_AT").write_text(retrieved_at.isoformat() + "\n")
    print(
        f"nights: {len(nights)} rows, {nights['geo'].nunique()} geos, "
        f"{nights['month'].min()}..{nights['month'].max()}"
    )
    print(
        f"pageviews: {len(pageviews)} rows, "
        f"{pageviews.groupby(['geo', 'series']).ngroups} article series"
    )
    print(
        f"gdelt: {len(gdelt)} rows, {gdelt['geo'].nunique()} geos, "
        f"{gdelt['month'].min()}..{gdelt['month'].max()}"
    )


if __name__ == "__main__":
    main()
