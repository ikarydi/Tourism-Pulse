"""Parse EUROCONTROL airport traffic files and OurAirports coordinates."""

import io
import math
from dataclasses import dataclass

import pandas as pd

FLIGHTS_URL = "https://www.eurocontrol.int/performance/data/download/csv/airport_traffic_{year}.csv"
FIRST_YEAR = 2016
# Public-domain airport list, only for coordinates (EUROCONTROL's files
# have none).
AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"

# EUROCONTROL state name -> Eurostat country code (Greece is EL), EU27 only:
# the app's country places are the EU27.
STATE_CODES: dict[str, str] = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czech Republic": "CZ", "Denmark": "DK", "Estonia": "EE",
    "Finland": "FI", "France": "FR", "Germany": "DE", "Greece": "EL",
    "Hungary": "HU", "Ireland": "IE", "Italy": "IT", "Latvia": "LV",
    "Lithuania": "LT", "Luxembourg": "LU", "Malta": "MT", "Netherlands": "NL",
    "Poland": "PL", "Portugal": "PT", "Romania": "RO", "Slovakia": "SK",
    "Slovenia": "SI", "Spain": "ES", "Sweden": "SE",
}  # fmt: skip

_COLUMNS = ["FLT_DATE", "APT_ICAO", "APT_NAME", "STATE_NAME", "FLT_ARR_1", "FLT_DEP_1"]


def monthly_airports(csv_texts: list[str]) -> pd.DataFrame:
    """Daily rows from one or more yearly files -> one row per airport and
    complete month: icao, airport, country, month (Period), arrivals,
    departures. A month is complete once the files reach its last day."""
    frames = [
        pd.read_csv(io.StringIO(text), usecols=_COLUMNS) for text in csv_texts if text.strip()
    ]
    if not frames:
        return pd.DataFrame(
            columns=["icao", "airport", "country", "month", "arrivals", "departures"]
        )
    daily = pd.concat(frames, ignore_index=True)
    daily = daily[daily["STATE_NAME"].isin(STATE_CODES)].copy()
    dates = pd.to_datetime(daily["FLT_DATE"])
    daily["month"] = dates.dt.to_period("M")
    last_day = dates.max()
    if pd.notna(last_day) and last_day.day != last_day.days_in_month:
        daily = daily[daily["month"] < last_day.to_period("M")]
    monthly = (
        daily.groupby(["APT_ICAO", "APT_NAME", "STATE_NAME", "month"], as_index=False)
        .agg(arrivals=("FLT_ARR_1", "sum"), departures=("FLT_DEP_1", "sum"))
        .rename(columns={"APT_ICAO": "icao", "APT_NAME": "airport"})
    )
    monthly["country"] = monthly.pop("STATE_NAME").map(STATE_CODES)
    return monthly[["icao", "airport", "country", "month", "arrivals", "departures"]]


def matched_growth(monthly: pd.DataFrame, icaos: set[str]) -> dict[pd.Period, float]:
    """Month -> change in arrivals against the same month a year earlier,
    over the airports in `icaos` that report arrivals in both months.
    EUROCONTROL's airport list grows over time (Italy from 13 to 49
    airports), so a plain total would count additions as growth."""
    rows = monthly[monthly["icao"].isin(icaos) & (monthly["arrivals"] > 0)]
    by_airport = rows.set_index(["icao", "month"])["arrivals"]
    growth: dict[pd.Period, float] = {}
    for month, block in rows.groupby("month"):
        now_total = before_total = 0.0
        for icao, arrivals in zip(block["icao"], block["arrivals"], strict=True):
            before = by_airport.get((icao, month - 12))
            if before is None:
                continue
            now_total += float(arrivals)
            before_total += float(before)
        if before_total > 0:
            growth[month] = now_total / before_total - 1
    return growth


@dataclass(frozen=True)
class Airport:
    icao: str
    latitude: float
    longitude: float
    # Scheduled passenger service (OurAirports): business and general
    # aviation fields such as Paris Le Bourget are not visitor gateways.
    scheduled: bool


def airport_coordinates(csv_text: str, icaos: set[str]) -> dict[str, Airport]:
    """OurAirports rows for the given ICAO codes (matched on ident, ICAO or
    GPS code)."""
    table = pd.read_csv(
        io.StringIO(csv_text),
        usecols=[
            "ident",
            "icao_code",
            "gps_code",
            "latitude_deg",
            "longitude_deg",
            "scheduled_service",
        ],
        dtype=str,
    )
    out: dict[str, Airport] = {}
    for column in ("ident", "icao_code", "gps_code"):
        for code, lat, lon, scheduled in zip(
            table[column],
            table["latitude_deg"],
            table["longitude_deg"],
            table["scheduled_service"],
            strict=True,
        ):
            if isinstance(code, str) and code in icaos and code not in out:
                try:
                    out[code] = Airport(code, float(lat), float(lon), scheduled == "yes")
                except (TypeError, ValueError):
                    continue
    return out


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def nearby(
    latitude: float, longitude: float, airports: dict[str, Airport], radius_km: float
) -> list[str]:
    return sorted(
        icao
        for icao, airport in airports.items()
        if distance_km(latitude, longitude, airport.latitude, airport.longitude) <= radius_km
    )
