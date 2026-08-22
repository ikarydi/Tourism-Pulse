"""Parsers for Eurostat's monthly tourism datasets.

https://ec.europa.eu/eurostat/databrowser/

Unlike KSH, this is not one country's statistical office - it's the EU's
own harmonized statistics API, covering every EU/EEA country with the same
schema and no API key. Its trade-off versus KSH: monthly cadence, but
country-level only (no Budapest-vs-Balaton style regional breakdown - see
`tour_occ_nin2m` for a NUTS2 regional variant, but that one only refreshes
annually, a real cadence downgrade). This adapter targets the KSH-style
monthly resolution and accepts the coarser (country-level) geography as the
trade-off, mirroring how `ingestion.ksh_capacity` already handles a
national-only source: attach it to a country-level Place, not a city one.

Four datasets are supported:

  tour_occ_nim   Nights spent at tourist accommodation establishments
                 (already the `demand` dimension's raw signal)
  tour_occ_arm   Arrivals at tourist accommodation establishments
                 (same shape as nights - raw/archival only, no dimension
                 wired to it yet; visible in the raw signal history)
  tour_occ_mnor  Net occupancy rate of bed-places (or bedrooms) in hotels
                 and similar accommodation - a percentage, feeding
                 `demand` via the generic normalize_percentage pathway
                 (the same convention "hotel_occupancy" already uses)
  tour_cap_nat   Bed-places in tourist accommodation establishments,
                 feeding `capacity` through the seasonal pathway - the same
                 dimension `ingestion.ksh_capacity` already produces for
                 Hungary, but its own signal_type
                 ("accommodation_capacity_annual", not KSH's
                 "accommodation_capacity"). Unlike the other three, this
                 dataset is published *annually*, not monthly (see the
                 dedicated annual parser below), and that signal_type split
                 is what lets it carry its own, much longer, half-life.

nights and arrivals share an identical JSON-stat dimension shape (freq,
c_resid, unit, nace_r2, geo, time) and are parsed by the same engine.
occupancy rate has a different shape (freq, accomunit, unit, geo, time -
no c_resid/nace_r2) and gets its own parse function, but both share the
same defensive "flat value index == time index" validation, since that
check is generic over whatever dimensions the response actually has.
Capacity reuses that same validation but has its own parse function,
since its `time` dimension is bare years ("2024"), not "YYYY-MM".

The response is Eurostat's JSON-stat 2.0 format: a `dimension` object
describing each queried dimension's categories, and a sparse `value` dict
keyed by flat integer index. Every dimension queried is fixed to exactly
one category *except* `time` (which varies), so the flat value index
equals the `time` dimension's own index - this is verified defensively
rather than assumed blindly (see `_assert_single_valued`).

One real gotcha: Eurostat's `geo` codes are not always ISO 3166-1 - Greece
is `EL` (not `GR`) and the United Kingdom is `UK` (not `GB`), following
Eurostat's own nomenclature rather than ISO's.
"""

import calendar
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

EUROSTAT_SOURCE_NAME = "eurostat"
EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

NIGHTS_DATASET = "tour_occ_nim"
NIGHTS_UNIT = "nights"
NIGHTS_BASE_URL = f"{EUROSTAT_API_BASE}/{NIGHTS_DATASET}"
EUROSTAT_DATASET = NIGHTS_DATASET  # backward-compatible alias
EUROSTAT_BASE_URL = NIGHTS_BASE_URL  # backward-compatible alias
EUROSTAT_PAGE_URL = "https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nim/default/table"

ARRIVALS_DATASET = "tour_occ_arm"
ARRIVALS_UNIT = "arrivals"
ARRIVALS_BASE_URL = f"{EUROSTAT_API_BASE}/{ARRIVALS_DATASET}"

OCCUPANCY_DATASET = "tour_occ_mnor"
OCCUPANCY_UNIT = "percent"
OCCUPANCY_BASE_URL = f"{EUROSTAT_API_BASE}/{OCCUPANCY_DATASET}"

CAPACITY_DATASET = "tour_cap_nat"
CAPACITY_UNIT = "bed_places"
CAPACITY_BASE_URL = f"{EUROSTAT_API_BASE}/{CAPACITY_DATASET}"

# Population on 1 January, by country - reference data (see
# db/models/place_demographics.py), not a Signal. Annual, same
# single-value-per-non-time-dimension shape as capacity, so it reuses
# `_parse_annual_country_series` unchanged.
POPULATION_DATASET = "demo_pjan"
POPULATION_UNIT = "people"
POPULATION_BASE_URL = f"{EUROSTAT_API_BASE}/{POPULATION_DATASET}"

# Tourism-sector (NACE I55 - accommodation) net turnover, year-over-year
# percentage change, calendar-adjusted. Annual, same shape as capacity/
# population.
ECONOMIC_DATASET = "sts_setu_a"
ECONOMIC_UNIT = "percent_yoy"
ECONOMIC_BASE_URL = f"{EUROSTAT_API_BASE}/{ECONOMIC_DATASET}"

# Fixed query dimensions for nights/arrivals (besides geo/time, which vary):
# monthly frequency, both residents and non-residents combined, raw count
# (not an index), and "hotels; holiday and other short-stay accommodation;
# camping" - the same accommodation scope KSH's combined total section
# covers.
EUROSTAT_FIXED_PARAMS: dict[str, str] = {
    "unit": "NR",
    "c_resid": "TOTAL",
    "nace_r2": "I551-I553",
}

# Fixed query dimensions for occupancy rate: percentage, bed-places (as
# opposed to bedrooms - matches the "how many people can be hosted" framing
# ingestion.ksh_capacity already uses for KSH's bed-places figure).
OCCUPANCY_FIXED_PARAMS: dict[str, str] = {
    "unit": "PC",
    "accomunit": "BEDPL",
}

# Fixed query dimensions for capacity: annual frequency (this dataset has no
# other), raw bed-place count, same accommodation scope as the others.
CAPACITY_FIXED_PARAMS: dict[str, str] = {
    "freq": "A",
    "unit": "NR",
    "accomunit": "BEDPL",
    "nace_r2": "I551-I553",
}

# Fixed query dimensions for population: total (all ages, both sexes), raw
# count. Verified live: demo_pjan's dims are freq/unit/age/sex/geo/time.
POPULATION_FIXED_PARAMS: dict[str, str] = {
    "freq": "A",
    "unit": "NR",
    "age": "TOTAL",
    "sex": "T",
}

# Fixed query dimensions for the economic (turnover growth) metric:
# accommodation sector (I55, matching EUROSTAT_FIXED_PARAMS' "I551-I553"
# scope in spirit), net turnover, year-over-year % change,
# calendar-adjusted. Verified live against sts_setu_a - unlike the
# other three metrics, HU itself has no published values for this
# combination (a genuine Eurostat data gap, not a query error - other
# countries like AT do), same "skip, don't invent" handling as any
# other unpublished period.
ECONOMIC_FIXED_PARAMS: dict[str, str] = {
    "freq": "A",
    "indic_bt": "NETTUR",
    "nace_r2": "I55",
    "s_adj": "CA",
    "unit": "PCH_SM",
}


@dataclass(frozen=True)
class EurostatObservation:
    """One monthly country-level observation from a Eurostat tourism dataset."""

    year: int
    month: int
    geo: str  # Eurostat geo code, e.g. "AT", "EL"
    geo_name: str  # e.g. "Austria", "Greece"
    value: Decimal
    unit: str
    period_start: date
    period_end: date

    @property
    def period(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def _period_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _assert_single_valued(dimension: dict, dim_order: list[str]) -> None:
    """Guard the "flat value index == time index" assumption every parser here relies on.

    Raises ValueError if any non-time dimension has more than one category -
    that would mean the flat value index no longer lines up 1:1 with the
    time dimension's own index, and parsing would silently misattribute
    values to the wrong month. Generic over whatever dimensions the
    response actually declares (via `dim_order`), so it applies unchanged
    to nights/arrivals (c_resid, nace_r2, ...) and occupancy rate
    (accomunit, ...) alike.
    """
    for dim_name in dim_order:
        if dim_name == "time":
            continue

        category_count = len(dimension[dim_name]["category"].get("index", {}))

        if category_count != 1:
            raise ValueError(
                f"Expected exactly one category for dimension {dim_name!r}, "
                f"got {category_count}. Query must fix every dimension "
                "except geo and time to a single value."
            )


def _parse_monthly_country_series(text: str, *, unit: str) -> list[EurostatObservation]:
    """Shared engine behind every Eurostat monthly-country-series parser here.

    Raises `ValueError` for an error response, an unexpected shape (see
    `_assert_single_valued`), or a response covering zero or more than one
    country (queries must fix `geo` to exactly one code). A month with no
    published value (sparse `value` dict has no entry for it) is skipped
    rather than invented.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Eurostat response is not valid JSON: {exc}") from exc

    if "error" in payload:
        raise ValueError(f"Eurostat API error: {payload['error']}")

    try:
        dimension = payload["dimension"]
        dim_order = payload["id"]
    except KeyError as exc:
        raise ValueError(f"Unexpected Eurostat response shape: missing {exc}") from exc

    _assert_single_valued(dimension, dim_order)

    geo_labels = dimension.get("geo", {}).get("category", {}).get("label", {})

    if len(geo_labels) != 1:
        raise ValueError(
            f"Expected exactly one geo in the response, got {len(geo_labels)}. "
            "Query must fix geo to a single country code."
        )

    geo_code, geo_name = next(iter(geo_labels.items()))

    time_index = dimension.get("time", {}).get("category", {}).get("index", {})
    values = payload.get("value", {})

    observations: list[EurostatObservation] = []

    for period, flat_index in time_index.items():
        raw = values.get(str(flat_index))

        if raw is None:
            # Month not yet published - do not invent a value.
            continue

        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            continue

        try:
            year_str, month_str = period.split("-", 1)
            year, month = int(year_str), int(month_str)
        except ValueError:
            continue

        period_start, period_end = _period_bounds(year, month)

        observations.append(
            EurostatObservation(
                year=year,
                month=month,
                geo=geo_code,
                geo_name=geo_name,
                value=value,
                unit=unit,
                period_start=period_start,
                period_end=period_end,
            )
        )

    observations.sort(key=lambda observation: (observation.year, observation.month))

    return observations


def _parse_annual_country_series(text: str, *, unit: str) -> list[EurostatObservation]:
    """Shared engine for annual (year-only) Eurostat country series, i.e. capacity.

    Same validation and error handling as `_parse_monthly_country_series`,
    but the `time` dimension is a bare year ("2024") rather than "YYYY-MM".
    Each observation is stamped as December of that year (month=12) so it
    flows through `pulse.seasonal_signal_adapter`'s "same calendar month"
    baseline logic unchanged - since every observation shares month=12,
    that check degenerates correctly into "prior years of the same annual
    series", which is exactly the comparison an annual figure needs.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Eurostat response is not valid JSON: {exc}") from exc

    if "error" in payload:
        raise ValueError(f"Eurostat API error: {payload['error']}")

    try:
        dimension = payload["dimension"]
        dim_order = payload["id"]
    except KeyError as exc:
        raise ValueError(f"Unexpected Eurostat response shape: missing {exc}") from exc

    _assert_single_valued(dimension, dim_order)

    geo_labels = dimension.get("geo", {}).get("category", {}).get("label", {})

    if len(geo_labels) != 1:
        raise ValueError(
            f"Expected exactly one geo in the response, got {len(geo_labels)}. "
            "Query must fix geo to a single country code."
        )

    geo_code, geo_name = next(iter(geo_labels.items()))

    time_index = dimension.get("time", {}).get("category", {}).get("index", {})
    values = payload.get("value", {})

    observations: list[EurostatObservation] = []

    for period, flat_index in time_index.items():
        raw = values.get(str(flat_index))

        if raw is None:
            # Year not yet published - do not invent a value.
            continue

        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            continue

        try:
            year = int(period)
        except ValueError:
            continue

        observations.append(
            EurostatObservation(
                year=year,
                month=12,
                geo=geo_code,
                geo_name=geo_name,
                value=value,
                unit=unit,
                period_start=date(year, 1, 1),
                period_end=date(year, 12, 31),
            )
        )

    observations.sort(key=lambda observation: (observation.year, observation.month))

    return observations


def parse_eurostat_capacity(text: str) -> list[EurostatObservation]:
    """Parse a Eurostat `tour_cap_nat` (bed-places) JSON-stat response.

    Annual, not monthly - see `_parse_annual_country_series`.
    """
    return _parse_annual_country_series(text, unit=CAPACITY_UNIT)


def parse_eurostat_tourism_nights(text: str) -> list[EurostatObservation]:
    """Parse a Eurostat `tour_occ_nim` (nights spent) JSON-stat response."""
    return _parse_monthly_country_series(text, unit=NIGHTS_UNIT)


def parse_eurostat_arrivals(text: str) -> list[EurostatObservation]:
    """Parse a Eurostat `tour_occ_arm` (tourist arrivals) JSON-stat response.

    Raw/archival only: no Pulse dimension is wired to arrivals yet (nights
    already drives `demand`) - this is additional evidence for lineage and
    the frontend's raw-signal view, per "preserve raw data".
    """
    return _parse_monthly_country_series(text, unit=ARRIVALS_UNIT)


def parse_eurostat_occupancy_rate(text: str) -> list[EurostatObservation]:
    """Parse a Eurostat `tour_occ_mnor` (net bed-place occupancy rate) JSON-stat response."""
    return _parse_monthly_country_series(text, unit=OCCUPANCY_UNIT)


def parse_eurostat_population(text: str) -> list[EurostatObservation]:
    """Parse a Eurostat `demo_pjan` (population on 1 January) JSON-stat
    response.

    Annual, not monthly - see `_parse_annual_country_series`. Reference
    data, not a Signal - see db/models/place_demographics.py.
    """
    return _parse_annual_country_series(text, unit=POPULATION_UNIT)


def parse_eurostat_turnover_growth(text: str) -> list[EurostatObservation]:
    """Parse a Eurostat `sts_setu_a` (accommodation-sector net turnover,
    year-over-year % change) JSON-stat response.

    Annual - see `_parse_annual_country_series`.
    """
    return _parse_annual_country_series(text, unit=ECONOMIC_UNIT)


def latest_observation(observations: list[EurostatObservation]) -> EurostatObservation | None:
    """Return the most recent published observation, or None if empty."""
    if not observations:
        return None

    return observations[-1]
