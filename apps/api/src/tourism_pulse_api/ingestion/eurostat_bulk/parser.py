"""Series definitions and JSON-stat parsing for the bulk Eurostat loader."""

import calendar
import math
from dataclasses import dataclass
from datetime import UTC, datetime

from tourism_pulse_api.ingestion.eu_locations.parser import EU27
from tourism_pulse_api.ingestion.eurostat_regional.parser import EUROSTAT_API_BASE, jsonstat_cells

EUROSTAT_SOURCE_NAME = "eurostat"
OFFICIAL_SCOPE = {"c_resid": "TOTAL", "nace_r2": "I551-I553"}
PLATFORM_SCOPE = {"indic_to": "NGT_SP", "c_resid": "TOTAL", "unit": "NR"}

# Place kinds a Eurostat code can map to (see service.place_index).
COUNTRY, REGION, AREA, CITY = "country", "region", "area", "city"


@dataclass(frozen=True)
class Series:
    key: str
    dataset: str
    filters: dict[str, str | tuple[str, ...]]
    since: str
    # signal_type per value of `split_dim` (or the single signal_type).
    signal_types: dict[str, tuple[str, str]]  # dim value -> (signal_type, unit)
    split_dim: str | None = None
    kinds: tuple[str, ...] = (COUNTRY, REGION, AREA)
    geo_dim: str = "geo"

    def url(self) -> str:
        params = "".join(
            f"&{key}={item}"
            for key, value in self.filters.items()
            for item in (value if isinstance(value, tuple) else (value,))
        )
        base = f"{EUROSTAT_API_BASE}/{self.dataset}?format=JSON&lang=EN"
        return f"{base}{params}&sinceTimePeriod={self.since}"


def _single(signal_type: str, unit: str) -> dict[str, tuple[str, str]]:
    return {"": (signal_type, unit)}


SERIES: list[Series] = [
    Series(
        "national_monthly_nights",
        "tour_occ_nim",
        {**OFFICIAL_SCOPE, "unit": "NR"},
        "2014-01",
        _single("tourism_nights", "nights"),
        kinds=(COUNTRY,),
    ),
    Series(
        "national_monthly_arrivals",
        "tour_occ_arm",
        {**OFFICIAL_SCOPE, "unit": "NR"},
        "2014-01",
        _single("tourist_arrivals", "arrivals"),
        kinds=(COUNTRY,),
    ),
    Series(
        "regional_monthly_nights",
        "tour_occ_nin2m",
        {**OFFICIAL_SCOPE, "unit": "NR"},
        "2020",
        _single("tourism_nights", "nights"),
        kinds=(REGION, AREA),
    ),
    Series(
        "regional_annual_nights",
        "tour_occ_nin2",
        {**OFFICIAL_SCOPE, "unit": "NR"},
        "2014",
        _single("tourism_nights_annual", "nights"),
    ),
    Series(
        "regional_bed_places",
        "tour_cap_nuts2",
        {"unit": "NR", "accomunit": "BEDPL", "nace_r2": "I551-I553"},
        "2014",
        _single("accommodation_capacity_annual", "bed_places"),
    ),
    Series(
        "platform_nights_nuts12",
        "tour_ce_omn12",
        {**PLATFORM_SCOPE, "month": "TOTAL"},
        "2018",
        _single("platform_nights_annual", "nights"),
        kinds=(COUNTRY, REGION),
    ),
    Series(
        "platform_nights_nuts3",
        "tour_ce_oan3",
        PLATFORM_SCOPE,
        "2018",
        _single("platform_nights_annual", "nights"),
        kinds=(AREA,),
    ),
    Series(
        "city_tourism",
        "urb_ctour",
        {"indic_ur": ("CR2001V", "CR2009V", "CR2011I", "CR2010V", "CR2011V", "CR1007V")},
        "2015",
        {
            "CR2001V": ("tourism_nights_annual", "nights"),
            "CR2009V": ("accommodation_capacity_annual", "bed_places"),
            "CR2011I": ("nights_per_resident_annual", "nights_per_resident"),
            "CR2010V": ("domestic_nights_annual", "nights"),
            "CR2011V": ("foreign_nights_annual", "nights"),
            "CR1007V": ("museum_visitors_annual", "visitors"),
        },
        split_dim="indic_ur",
        kinds=(CITY,),
        geo_dim="cities",
    ),
]

POPULATION = Series(
    "population",
    "demo_r_pjanaggr3",
    {"sex": "T", "age": "TOTAL", "unit": "NR"},
    "2014",
    _single("population", "residents"),
)


@dataclass(frozen=True)
class Record:
    code: str
    signal_type: str
    unit: str
    observed_at: datetime
    value: float


def _period_end(time: str, month: str | None) -> datetime | None:
    try:
        if month and month.startswith("M"):
            year, month_number = int(time), int(month[1:])
        elif "-" in time:
            year, month_number = int(time[:4]), int(time[5:7])
        else:
            return datetime(int(time), 12, 31, tzinfo=UTC)
    except ValueError:
        return None
    last = calendar.monthrange(year, month_number)[1]
    return datetime(year, month_number, last, tzinfo=UTC)


def parse_series(series: Series, payload: dict) -> list[Record]:
    records = []
    for cell, value in jsonstat_cells(payload):
        code = cell.get(series.geo_dim, "")
        if "_" in code or len(code) < 2 or code[:2] not in EU27:
            continue
        if not math.isfinite(value) or value < 0:
            continue
        month = cell.get("month")
        if month == "TOTAL" and series.dataset == "tour_occ_nin2m":
            continue  # the yearly total; months are loaded individually
        mapping = series.signal_types.get(
            cell.get(series.split_dim, "") if series.split_dim else ""
        )
        if mapping is None:
            continue
        observed_at = _period_end(cell["time"], month)
        if observed_at is None:
            continue
        signal_type, unit = mapping
        records.append(Record(code, signal_type, unit, observed_at, value))
    return records
