"""Parsers for Eurostat's regional tourism datasets (JSON-stat 2.0)."""

import itertools
import math
from dataclasses import dataclass

EUROSTAT_SOURCE_NAME = "eurostat"
EUROSTAT_API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

NIGHTS_REGIONAL_DATASET = "tour_occ_nin2"
NIGHTS_REGIONAL_MONTHLY_DATASET = "tour_occ_nin2m"

# Same accommodation scope as the national nights adapter: hotels,
# holiday and other short-stay accommodation, camping.
_SCOPE = {"c_resid": "TOTAL", "nace_r2": "I551-I553"}

INDICATOR_UNITS = {
    "tourism_intensity": "nights_per_1000_residents",
    "tourism_density": "nights_per_km2",
    "seasonality_peak_share": "share_of_annual_nights",
}

_UNIT_TO_INDICATOR = {"P_THAB": "tourism_intensity", "P_KM2": "tourism_density"}


@dataclass(frozen=True)
class IndicatorValue:
    nuts_code: str
    indicator: str
    year: int
    value: float


def dataset_url(dataset: str, *, units: tuple[str, ...], since_year: int) -> str:
    unit_params = "".join(f"&unit={unit}" for unit in units)
    scope = "".join(f"&{key}={value}" for key, value in _SCOPE.items())
    return (
        f"{EUROSTAT_API_BASE}/{dataset}?format=JSON&lang=EN{scope}{unit_params}"
        f"&sinceTimePeriod={since_year}"
    )


def _is_region(geo: str) -> bool:
    """NUTS 0-3 codes only; EU-wide aggregates (EU27_2020, ...) are not regions."""
    return "_" not in geo and 2 <= len(geo) <= 5


def _cells(payload: dict) -> list[tuple[dict[str, str], float]]:
    """Decode a JSON-stat cube into ({dimension: category}, value) cells."""
    try:
        ids = payload["id"]
        sizes = payload["size"]
        dimensions = payload["dimension"]
        values = payload["value"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Not a JSON-stat dataset: missing {exc}") from exc

    categories = []
    for dim, size in zip(ids, sizes, strict=True):
        index = dimensions[dim]["category"]["index"]
        by_position = {position: code for code, position in index.items()}
        if len(by_position) != size:
            raise ValueError(f"JSON-stat dimension {dim!r} has {len(by_position)} != {size}")
        categories.append([by_position[i] for i in range(size)])

    cells = []
    # JSON-stat flattens the cube row-major over `ids`; values is sparse.
    for flat, combination in enumerate(itertools.product(*categories)):
        raw = values.get(str(flat)) if isinstance(values, dict) else values[flat]
        if raw is None:
            continue
        cells.append((dict(zip(ids, combination, strict=True)), float(raw)))
    return cells


def parse_intensity_density(payload: dict) -> list[IndicatorValue]:
    rows = []
    for cell, value in _cells(payload):
        indicator = _UNIT_TO_INDICATOR.get(cell.get("unit", ""))
        if indicator is None or not _is_region(cell["geo"]):
            continue
        if not math.isfinite(value) or value < 0:
            continue
        rows.append(IndicatorValue(cell["geo"], indicator, int(cell["time"]), value))
    return rows


def parse_seasonality(payload: dict) -> list[IndicatorValue]:
    """Peak-month share per region and year, only for complete years."""
    monthly: dict[tuple[str, int], dict[str, float]] = {}
    for cell, value in _cells(payload):
        month = cell.get("month", "")
        if cell.get("unit") != "NR" or not month.startswith("M") or value < 0:
            continue
        if not _is_region(cell["geo"]):
            continue
        monthly.setdefault((cell["geo"], int(cell["time"])), {})[month] = value

    rows = []
    for (geo, year), months in monthly.items():
        total = sum(months.values())
        if len(months) != 12 or total <= 0:
            continue
        peak_share = max(months.values()) / total
        rows.append(IndicatorValue(geo, "seasonality_peak_share", year, peak_share))
    return rows
