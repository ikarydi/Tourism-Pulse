"""Parser for the KSH STADAT 27.2.1.19 CSV export.

"Tourism nights at tourist accommodation establishments in Budapest and by
tourism areas (monthly data)"
https://www.ksh.hu/stadat_files/tur/en/tur0081.html

KSH offers this table as CSV and XLSX downloads. The CSV is the most stable
machine-readable option (no spreadsheet-format parsing, no merged cells), so
that is what this adapter reads.

Layout of the CSV
------------------
The file stacks three sections, one below another, each covering the same
year/month grid but a different accommodation scope:

  1. "Nights at commercial accommodation establishments, thousands"
  2. "Nights at private and other accommodation establishments, thousands"
  3. "Nights at tourist accommodation establishments, thousands"
     (commercial + private combined - KSH's headline total)

This parser only reads section 3, since that is KSH's headline "total
tourism nights" series - domestic and international nights across *all*
accommodation types, not just one segment of them.

Each section also ends with a year-to-date row (Month == "JanuaryJune") and a
"Corresponding period of previous year = 100.0%" block of year-over-year
*percentage* rows sharing the same Year/Month labels as real observations.
Both are skipped: they are not absolute monthly nights figures.

Within each of those three sections, KSH breaks nights down by tourism area
(Budapest, Balaton, Debrecen and surroundings, ...) in three parallel column
blocks - domestic, international, and total - each area at the same relative
offset within its block. `SUPPORTED_REGIONS` maps a short region key to that
offset, so any of KSH's tourism areas can be selected, not just Budapest.

Total tourism nights for a region is *calculated* here (domestic +
international) rather than trusted from the file's own "Tourism nights
total <area>" column, per the requirement to compute the total explicitly.
"""

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

KSH_SOURCE_NAME = "ksh"
KSH_TABLE_ID = "27.2.1.19"
KSH_CSV_URL = "https://www.ksh.hu/stadat_files/tur/en/tur0081.csv"
KSH_PAGE_URL = "https://www.ksh.hu/stadat_files/tur/en/tur0081.html"

DEFAULT_REGION = "budapest"
NIGHTS_UNIT = "thousand_nights"

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
class RegionColumns:
    """Where one KSH tourism area lives within each 13-column block."""

    place_name: str
    offset: int  # 0-indexed position within a 13-column domestic/international block


# Position of each tourism area within a block, taken directly from the CSV
# header order: Total, Balaton, Budapest, Greater Budapest, Bük and Sárvár,
# Debrecen and surroundings, Győr and Pannonhalma, Gyula region, Eger region,
# Pécs region, Sopron region, Szeged region, Tokaj and Nyíregyháza.
SUPPORTED_REGIONS: dict[str, RegionColumns] = {
    "balaton": RegionColumns("Balaton", 1),
    "budapest": RegionColumns("Budapest", 2),
    "greater_budapest": RegionColumns("Greater Budapest", 3),
    "buk_sarvar": RegionColumns("Bük and Sárvár", 4),
    "debrecen": RegionColumns("Debrecen", 5),
    "gyor_pannonhalma": RegionColumns("Győr and Pannonhalma", 6),
    "gyula": RegionColumns("Gyula", 7),
    "eger": RegionColumns("Eger", 8),
    "pecs": RegionColumns("Pécs", 9),
    "sopron": RegionColumns("Sopron", 10),
    "szeged": RegionColumns("Szeged", 11),
    "tokaj_nyiregyhaza": RegionColumns("Tokaj and Nyíregyháza", 12),
}

_BLOCK_SIZE = 13
_DOMESTIC_BASE_COLUMN = 2  # fields[2] = "Domestic tourism nights Total"
_INTERNATIONAL_BASE_COLUMN = 2 + _BLOCK_SIZE  # fields[15] = "International ... Total"
_MIN_DATA_COLUMNS = 2 + 3 * _BLOCK_SIZE  # Year, Month + domestic + international + total blocks

_TOTAL_SECTION_MARKER = "nights at tourist accommodation establishments"
_ACCOMMODATION_SECTION_MARKER = "accommodation establishments"
_INDEX_BLOCK_MARKER = "corresponding period of previous year"


@dataclass(frozen=True)
class KshObservation:
    """One monthly tourism-nights observation for one KSH tourism area."""

    year: int
    month: int
    region: str  # key into SUPPORTED_REGIONS
    domestic_nights: Decimal
    international_nights: Decimal
    total_nights: Decimal
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
    no-break) - e.g. "1 527" - and leaves future/unpublished months blank.
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


def _resolve_regions(regions: Iterable[str] | None) -> dict[str, RegionColumns]:
    if regions is None:
        return SUPPORTED_REGIONS

    resolved: dict[str, RegionColumns] = {}

    for region in regions:
        try:
            resolved[region] = SUPPORTED_REGIONS[region]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported KSH region {region!r}. "
                f"Supported regions: {sorted(SUPPORTED_REGIONS)}"
            ) from exc

    return resolved


def parse_ksh_csv(
    text: str,
    *,
    regions: Iterable[str] | None = None,
) -> list[KshObservation]:
    """Parse the KSH STADAT 27.2.1.19 CSV export into tourism-nights observations.

    `regions` selects which KSH tourism areas to extract (keys of
    `SUPPORTED_REGIONS`, e.g. `["budapest", "debrecen"]`). Defaults to every
    supported region. Raises `ValueError` for an unrecognized region key.

    Only real, published monthly observations from the combined
    (commercial + private) total section are returned, sorted chronologically
    (ties across regions are not ordered relative to each other). Section
    headers, year-to-date rows, and year-over-year percentage rows are
    skipped. A region/month with no published value (blank cell) is skipped
    rather than invented, independently of whether other regions in the same
    row are published.
    """
    selected_regions = _resolve_regions(regions)

    lines = [line for line in text.splitlines() if line.strip()]

    if len(lines) < 2:
        return []

    observations: list[KshObservation] = []
    in_total_section = False
    in_index_block = False
    current_year: int | None = None

    for line in lines[2:]:  # skip the table title row and the column header row
        fields = line.split(";")

        if len(fields) < _MIN_DATA_COLUMNS:
            continue

        col_year = fields[0].strip()
        col_month = fields[1].strip()

        if not col_month:
            marker = col_year.lower()

            if _TOTAL_SECTION_MARKER in marker:
                in_total_section = True
                in_index_block = False
            elif _ACCOMMODATION_SECTION_MARKER in marker:
                # A different section (commercial-only or private-only).
                in_total_section = False
                in_index_block = False
            elif _INDEX_BLOCK_MARKER in marker:
                in_index_block = True

            continue

        if col_year:
            if not col_year.isdigit():
                # Not a real year label sharing the Month column by accident.
                continue

            current_year = int(col_year)

        month_number = _MONTH_NUMBERS.get(col_month)

        if (
            not in_total_section
            or in_index_block
            or month_number is None
            or current_year is None
        ):
            continue

        period_start, period_end = _period_bounds(current_year, month_number)

        for region_key, columns in selected_regions.items():
            domestic = _clean_number(fields[_DOMESTIC_BASE_COLUMN + columns.offset])
            international = _clean_number(
                fields[_INTERNATIONAL_BASE_COLUMN + columns.offset]
            )

            if domestic is None or international is None:
                # Month not yet published for this region - do not invent a value.
                continue

            observations.append(
                KshObservation(
                    year=current_year,
                    month=month_number,
                    region=region_key,
                    domestic_nights=domestic,
                    international_nights=international,
                    total_nights=domestic + international,
                    unit=NIGHTS_UNIT,
                    place_name=columns.place_name,
                    period_start=period_start,
                    period_end=period_end,
                )
            )

    observations.sort(key=lambda observation: (observation.year, observation.month))

    return observations


def latest_observation(observations: list[KshObservation]) -> KshObservation | None:
    """Return the most recent published observation, or None if empty.

    Assumes `observations` has already been narrowed to a single region -
    chronological ordering does not otherwise distinguish between regions.
    """
    if not observations:
        return None

    return observations[-1]
