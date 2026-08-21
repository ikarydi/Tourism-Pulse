SOURCE_RELIABILITY: dict[str, float] = {
    "government": 1.00,
    "official": 1.00,
    "ksh": 1.00,
    # The EU's own harmonized statistics office, aggregating national
    # statistical offices' official figures - same tier as "government".
    "eurostat": 1.00,
    # Aggregates multiple national meteorological services' models
    # (ECMWF, DWD, NOAA, ...) - highly reliable, but not a primary
    # government source itself, so scored just below "official".
    "open-meteo": 0.95,
    "airport": 0.98,
    "airline": 0.98,
    "hotel": 0.95,
    "booking": 0.95,
    "commercial": 0.90,
    # A commercial ticketing platform, not the event organizer itself -
    # generally accurate for listed events, but not authoritative in the
    # way a government/official source is.
    "ticketmaster": 0.90,
    "news": 0.85,
    "social": 0.65,
    "unknown": 0.40,
}


def get_source_reliability(source: str) -> float:
    return SOURCE_RELIABILITY.get(
        source.strip().lower(),
        SOURCE_RELIABILITY["unknown"],
    )
