"""KSH (Hungarian Central Statistical Office) accommodation-capacity ingestion.

Source table: STADAT 27.2.1.13 "Capacity of tourist accommodation
establishments by type (monthly data)".
https://www.ksh.hu/stadat_files/tur/en/tur0071.html

Hungary-wide only (no regional breakdown) - see `parser.SUPPORTED_METRICS`
for the figures available (units in operation, bedrooms, bed-places).
"""

from tourism_pulse_api.ingestion.ksh_capacity.parser import (
    CAPACITY_PLACE_NAME,
    DEFAULT_METRIC,
    KSH_CSV_URL,
    KSH_SOURCE_NAME,
    SUPPORTED_METRICS,
    KshCapacityObservation,
    MetricColumn,
    parse_ksh_capacity_csv,
)

__all__ = [
    "CAPACITY_PLACE_NAME",
    "DEFAULT_METRIC",
    "KSH_CSV_URL",
    "KSH_SOURCE_NAME",
    "KshCapacityObservation",
    "MetricColumn",
    "SUPPORTED_METRICS",
    "parse_ksh_capacity_csv",
]
