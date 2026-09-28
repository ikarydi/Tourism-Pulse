"""Build the Gate 3 data snapshots. See PREREGISTRATION.md.

    python -m research.gate3.fetch

Writes, next to this file:

- data/flights.csv: Eurocontrol IFR arrivals and departures per airport and
  month (daily files summed), with the Eurostat code of the airport's
  country. From the yearly files at
  https://www.eurocontrol.int/performance/data/download/csv/airport_traffic_<year>.csv
- data/hotel_survey.csv: the European Commission's services survey for
  accommodation (NACE 55), monthly balances, not seasonally adjusted, per
  country.
- data/RETRIEVED_AT: when both were downloaded.

Downloads are cached in data/*_cache/ (not committed).
"""

import io
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
FLIGHTS_CACHE = DATA_DIR / "eurocontrol_cache"
SURVEY_CACHE = DATA_DIR / "survey_cache"
USER_AGENT = "TourismPulse/1.0 (https://github.com/ikarydi/Tourism-Pulse)"

FLIGHTS_URL = "https://www.eurocontrol.int/performance/data/download/csv/airport_traffic_{year}.csv"
FIRST_YEAR = 2016
# The survey's download folder is named after its release (yymm).
SURVEY_URL = (
    "https://ec.europa.eu/economy_finance/db_indicators/surveys/documents/series/"
    "nace2_ecfin_{release}/services_subsectors_nsa_nace2.zip"
)
SURVEY_RELEASE = "2608"

# Eurocontrol state name -> Eurostat code, for the 30 Gate 1-2 countries.
STATES = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czech Republic": "CZ", "Denmark": "DK", "Estonia": "EE",
    "Finland": "FI", "France": "FR", "Germany": "DE", "Greece": "EL",
    "Hungary": "HU", "Iceland": "IS", "Ireland": "IE", "Italy": "IT",
    "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU", "Malta": "MT",
    "Netherlands": "NL", "Norway": "NO", "Poland": "PL", "Portugal": "PT",
    "Romania": "RO", "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES",
    "Sweden": "SE", "Switzerland": "CH",
}  # fmt: skip
# Survey questions for accommodation (NACE 55), balances in points.
SURVEY_QUESTIONS = {
    "COF": "confidence",
    "1": "business_past",
    "2": "demand_past",
    "3": "demand_expected",
    "5": "employment_expected",
    "6": "prices_expected",
}


def _download(url: str, path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
            path.write_bytes(response.read())
    return path


def flights(last_year: int) -> pd.DataFrame:
    frames = []
    for year in range(FIRST_YEAR, last_year + 1):
        path = _download(
            FLIGHTS_URL.format(year=year), FLIGHTS_CACHE / f"airport_traffic_{year}.csv"
        )
        frames.append(
            pd.read_csv(
                path,
                encoding="utf-8-sig",
                usecols=[
                    "FLT_DATE",
                    "APT_ICAO",
                    "APT_NAME",
                    "STATE_NAME",
                    "FLT_ARR_1",
                    "FLT_DEP_1",
                ],
            )
        )
    daily = pd.concat(frames, ignore_index=True)
    daily = daily[daily["STATE_NAME"].isin(STATES)]
    daily["month"] = pd.to_datetime(daily["FLT_DATE"]).dt.to_period("M").astype(str)
    monthly = (
        daily.groupby(["STATE_NAME", "APT_ICAO", "APT_NAME", "month"], as_index=False)
        .agg(
            days=("FLT_DATE", "nunique"),
            arrivals=("FLT_ARR_1", "sum"),
            departures=("FLT_DEP_1", "sum"),
        )
        .rename(columns={"APT_ICAO": "icao", "APT_NAME": "airport"})
    )
    monthly.insert(0, "geo", monthly.pop("STATE_NAME").map(STATES))
    return monthly.sort_values(["geo", "icao", "month"]).reset_index(drop=True)


def hotel_survey() -> pd.DataFrame:
    path = _download(
        SURVEY_URL.format(release=SURVEY_RELEASE),
        SURVEY_CACHE / f"services_subsectors_nsa_nace2_{SURVEY_RELEASE}.zip",
    )
    with zipfile.ZipFile(path) as archive:
        sheet = pd.read_excel(
            io.BytesIO(archive.read("services_subsectors_nsa_m_nace2.xlsx")), sheet_name="55"
        )
    sheet = sheet.rename(columns={"55": "month"})
    sheet["month"] = pd.to_datetime(sheet["month"]).dt.to_period("M").astype(str)
    rows = []
    for geo in sorted(set(STATES.values())):
        columns = {
            f"SERV.{geo}.55.{code}.B.M": name
            for code, name in SURVEY_QUESTIONS.items()
            if f"SERV.{geo}.55.{code}.B.M" in sheet
        }
        if not columns:
            continue
        block = (
            sheet[["month", *columns]]
            .rename(columns=columns)
            .dropna(how="all", subset=list(columns.values()))
        )
        rows.append(block.assign(geo=geo))
    survey = pd.concat(rows, ignore_index=True)
    return survey[["geo", "month", *SURVEY_QUESTIONS.values()]].sort_values(["geo", "month"])


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    now = datetime.now(UTC)
    flight_table = flights(now.year)
    flight_table.to_csv(DATA_DIR / "flights.csv", index=False)
    survey_table = hotel_survey()
    survey_table.to_csv(DATA_DIR / "hotel_survey.csv", index=False, float_format="%.1f")
    (DATA_DIR / "RETRIEVED_AT").write_text(
        f"{now:%Y-%m-%dT%H:%M:%SZ}\n"
        f"eurocontrol airport_traffic {FIRST_YEAR}-{now.year}\n"
        f"ec services survey release {SURVEY_RELEASE}\n"
    )
    print(
        f"flights: {len(flight_table)} airport-months, {flight_table['geo'].nunique()} countries, "
        f"{flight_table['month'].min()}..{flight_table['month'].max()}"
    )
    print(
        f"hotel survey: {len(survey_table)} country-months, {survey_table['geo'].nunique()} "
        f"countries, {survey_table['month'].min()}..{survey_table['month'].max()}"
    )


if __name__ == "__main__":
    main()
