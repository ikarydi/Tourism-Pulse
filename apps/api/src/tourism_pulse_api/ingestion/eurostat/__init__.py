"""Eurostat tourism-nights ingestion (tour_occ_nim).

https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nim/default/table

Free, keyless, EU-wide - covers every EU/EEA country with one adapter,
country-level, monthly. Complements (does not replace) country-specific
adapters like KSH, which offer city/regional granularity KSH-covered
countries KSH offers that Eurostat cannot.
"""

from tourism_pulse_api.ingestion.eurostat.parser import (
    EUROSTAT_SOURCE_NAME,
    EurostatObservation,
    parse_eurostat_tourism_nights,
)

__all__ = [
    "EUROSTAT_SOURCE_NAME",
    "EurostatObservation",
    "parse_eurostat_tourism_nights",
]
