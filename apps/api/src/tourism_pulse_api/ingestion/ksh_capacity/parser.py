"""Parser for the KSH STADAT 27.2.1.13 CSV export.

"Capacity of tourist accommodation establishments by type (monthly data)"
https://www.ksh.hu/stadat_files/tur/en/tur0071.html

Unlike the tourism-nights table (27.2.1.19), this table has no regional
breakdown - it is a single, Hungary-wide series broken down by accommodation
*type* (hotels, boarding houses, community hostels, bungalow complexes,
camping sites) and ownership category (commercial / private / other), across
three metrics: number of units in operation, number of bedrooms, and number
of bed-places. There is no separate "commercial vs. private vs. total"
section stack either - all three metrics sit side by side in one table.

This parser reads the grand-total column for each metric ("... Tourist
accommodation establishments, total" - commercial + private + other
combined), selectable via `SUPPORTED_METRICS`. The default, `bed_places`, is
what "capacity" means for tourism purposes: how many people the destination
can accommodate.

The CSV's header row uses RFC4180 quoting with an embedded newline inside
three column names (e.g. `"...establishments\\ntotal"`), so this parser reads
rows with the standard library `csv` module rather than naive line-splitting
(which is what the tourism-nights parser does - safe there only because that
header has no quoted fields).

As with tourism nights, a "Corresponding period of previous year = 100.0%"
block of year-over-year percentage rows follows the real data and shares the
same Year/Month labels - it is skipped, along with blank (not yet published)
months.
"""

import calendar
import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

KSH_SOURCE_NAME = "ksh"
KSH_TABLE_ID = "27.2.1.13"
KSH_CSV_URL = "https://www.ksh.hu/stadat_files/tur/en/tur0071.csv"
KSH_PAGE_URL = "https://www.ksh.hu/stadat_files/tur/en/tur0071.html"

CAPACITY_PLACE_NAME = "Hungary"
DEFAULT_METRIC = "bed_places"

_MONTH_NUMBERS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


@dataclass(frozen=True)
class MetricColumn:
    """Where one capacity metric's grand-total column lives, and its unit."""

    column: int  # 0-indexed absolute column of the "... total" figure
    unit: str


# Each metric block is 10 columns wide (Hotels, Boarding houses, Community
# hostels, Bungalow complexes, Camping sites, Commercial total, Private,
# Other, Private+other total, Grand total) starting right after Year/Month.
# The grand-total column is the last of each block.
SUPPORTED_METRICS: dict[str, MetricColumn] = {
    "units": MetricColumn(column=11, unit="establishments"),
    "bedrooms": MetricColumn(column=21, unit="bedrooms"),
    "bed_places": MetricColumn(column=31, unit="beds"),
}

_INDEX_BLOCK_MARKER = "corresponding period of previous year"


@dataclass(frozen=True)
class KshCapacityObservation:
    """One monthly Hungary-wide accommodation-capacity observation."""

    year: int
    month: int
    metric: str  # key into SUPPORTED_METRICS
    value: Decimal
    unit: str
    place_name: str
    period_start: date
    period_end: date

    @property
    def period(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def _clean_number(raw: str) -> Decimal | None:
    """Parse a KSH numeric cell, or return None if it is blank/unpublished/unparsable.

    KSH separates thousands with spaces (regular, non-breaking, or narrow
    no-break) and leaves future/unpublished months blank.
    """
    text = (
        raw.strip()
        .replace(" ", "")
        .replace(" ", "")
        .replace(" ", "")
    )

    if not text:
        return None

    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _period_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def parse_ksh_capacity_csv(
    text: str,
    *,
    metric: str = DEFAULT_METRIC,
) -> list[KshCapacityObservation]:
    """Parse the KSH STADAT 27.2.1.13 CSV export into capacity observations.

    `metric` selects which grand-total column to read (a key of
    `SUPPORTED_METRICS`). Raises `ValueError` for an unrecognized metric key.

    Only real, published monthly values are returned, sorted chronologically.
    The year-over-year percentage block is skipped, and a blank cell (month
    not yet published) is skipped rather than invented.
    """
    try:
        metric_column = SUPPORTED_METRICS[metric]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported KSH capacity metric {metric!r}. "
            f"Supported metrics: {sorted(SUPPORTED_METRICS)}"
        ) from exc

    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)

    if len(rows) < 2:
        return []

    observations: list[KshCapacityObservation] = []
    in_index_block = False
    current_year: int | None = None

    for row in rows[2:]:  # skip the table title row and the column header row
        if len(row) <= metric_column.column:
            continue

        col_year = row[0].strip()
        col_month = row[1].strip()

        if not col_month:
            # e.g. the "Corresponding period of previous year = 100.0%" marker.
            if _INDEX_BLOCK_MARKER in col_year.lower():
                in_index_block = True
            continue

        if col_year:
            if not col_year.isdigit():
                continue

            current_year = int(col_year)
            # Note: unlike the tourism-nights table, this one has a single
            # data block followed by a single trailing index block with no
            # further sections after it, so in_index_block is never reset
            # back to False once set - everything from that marker to EOF
            # is percentage rows, not observations.

        month_number = _MONTH_NUMBERS.get(col_month)

        if in_index_block or month_number is None or current_year is None:
            continue

        value = _clean_number(row[metric_column.column])

        if value is None:
            # Month not yet published - do not invent a value.
            continue

        period_start, period_end = _period_bounds(current_year, month_number)

        observations.append(
            KshCapacityObservation(
                year=current_year,
                month=month_number,
                metric=metric,
                value=value,
                unit=metric_column.unit,
                place_name=CAPACITY_PLACE_NAME,
                period_start=period_start,
                period_end=period_end,
            )
        )

    observations.sort(key=lambda observation: (observation.year, observation.month))

    return observations


def latest_observation(
    observations: list[KshCapacityObservation],
) -> KshCapacityObservation | None:
    """Return the most recent published observation, or None if empty."""
    if not observations:
        return None

    return observations[-1]
