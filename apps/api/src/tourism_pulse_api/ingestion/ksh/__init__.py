"""KSH (Hungarian Central Statistical Office) tourism-nights ingestion.

Source table: STADAT 27.2.1.19 "Tourism nights at tourist accommodation
establishments in Budapest and by tourism areas (monthly data)".
https://www.ksh.hu/stadat_files/tur/en/tur0081.html

Covers Budapest and every other Hungarian tourism area KSH tracks in the
same table (Balaton, Debrecen, Pécs, ...) - see `SUPPORTED_REGIONS`.
"""

from tourism_pulse_api.ingestion.ksh.parser import (
    DEFAULT_REGION,
    KSH_CSV_URL,
    KSH_SOURCE_NAME,
    SUPPORTED_REGIONS,
    KshObservation,
    RegionColumns,
    parse_ksh_csv,
)

__all__ = [
    "DEFAULT_REGION",
    "KSH_CSV_URL",
    "KSH_SOURCE_NAME",
    "KshObservation",
    "RegionColumns",
    "SUPPORTED_REGIONS",
    "parse_ksh_csv",
]
