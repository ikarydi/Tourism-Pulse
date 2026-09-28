"""Parse the Commission's services sub-sector workbook."""

import io
import math
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pandas as pd

from tourism_pulse_api.ingestion.eu_locations.parser import EU27

# Folder per monthly release, named yymm.
SURVEY_URL = (
    "https://ec.europa.eu/economy_finance/db_indicators/surveys/documents/series/"
    "nace2_ecfin_{release}/services_subsectors_nsa_nace2.zip"
)
WORKBOOK = "services_subsectors_nsa_m_nace2.xlsx"
SINCE = "2010-01"

# (sheet, question code) -> (signal_type, what the balance measures)
QUESTIONS: dict[tuple[str, str], str] = {
    ("55", "COF"): "hotel_confidence",
    ("55", "2"): "hotel_demand_past",
    ("55", "3"): "hotel_demand_expected",
    ("55", "5"): "hotel_employment_expected",
    ("55", "6"): "hotel_prices_expected",
    ("79", "COF"): "travel_trade_confidence",
    ("79", "3"): "travel_trade_demand_expected",
}
UNIT = "balance"


def release_candidates(today: date, months_back: int = 3) -> list[str]:
    """yymm folder names to try, newest first: this month's release may
    not be out yet."""
    out = []
    year, month = today.year, today.month
    for _ in range(months_back + 1):
        out.append(f"{year % 100:02d}{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return out


@dataclass(frozen=True)
class Balance:
    country: str
    signal_type: str
    observed_at: datetime
    value: float


def _month_end(period: pd.Period) -> datetime:
    return datetime(period.year, period.month, period.days_in_month, tzinfo=UTC)


def parse_workbook(zip_bytes: bytes) -> list[Balance]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        workbook = io.BytesIO(archive.read(WORKBOOK))
    sheets = pd.read_excel(workbook, sheet_name=sorted({sheet for sheet, _ in QUESTIONS}))
    since = pd.Period(SINCE, "M")
    balances = []
    for sheet_name, sheet in sheets.items():
        first = sheet.columns[0]
        months = pd.to_datetime(sheet[first], errors="coerce").dt.to_period("M")
        for column in sheet.columns[1:]:
            parts = str(column).split(".")
            # SERV.<country>.<sector>.<question>.B.M
            if len(parts) != 6 or parts[0] != "SERV" or parts[1] not in EU27:
                continue
            signal_type = QUESTIONS.get((sheet_name, parts[3]))
            if signal_type is None:
                continue
            for month, value in zip(months, sheet[column], strict=True):
                if pd.isna(month) or month < since:
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(number):
                    balances.append(Balance(parts[1], signal_type, _month_end(month), number))
    return balances
