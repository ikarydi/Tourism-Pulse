from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.engine import SignalInput

DIMENSION_MAP: dict[str, str] = {
    "demand": "demand",
    "capacity": "capacity",
    "event": "events",
    "events": "events",
    "environment": "environment",
    "occupancy": "demand",
    "hotel_occupancy": "demand",
    "sentiment": "demand",
    "weather_comfort": "environment",
    "tourism_nights": "demand",
    "accommodation_capacity": "capacity",
    "accommodation_capacity_annual": "capacity",
    "occupancy_rate": "demand",
    "hotel_count": "capacity",
    "restaurant_count": "capacity",
    # YouTube search-result counts - grouped with demand alongside
    # sentiment/occupancy/tourism_nights as another piece of demand-side
    # evidence (spec section 6.3 lists search_interest explicitly).
    "search_interest": "demand",
    # GDELT news coverage volume and tone - see pulse.news_mentions /
    # pulse.news_sentiment. Grouped with demand for the same reason as
    # search_interest above.
    "news_mentions": "demand",
    "news_sentiment": "demand",
    # OpenSky airborne-aircraft count near a destination - a live proxy
    # for transport activity (spec 6.3's airport_arrivals in spirit, not
    # literally a per-period arrivals count - see pulse.airport_traffic).
    "airport_traffic": "demand",
    # Wikipedia 30-day pageview total - a second, independent attention
    # signal alongside search_interest. See pulse.wikipedia_interest for
    # why it's a distinct signal_type rather than reusing search_interest.
    "wikipedia_pageviews": "demand",
    # GDACS current highest disaster-alert score for a place's country -
    # the first signal to feed the `risk` dimension. See
    # pulse.disaster_risk for its (inverted-polarity) normalizer.
    "disaster_alert_severity": "risk",
    # OpenAQ nearest-station PM2.5 reading - fills the spec's Environment
    # source category alongside weather_comfort. See pulse.air_quality
    # for its (inverted-polarity) normalizer.
    "air_quality_pm25": "environment",
}


def signal_to_input(
    signal: Signal,
    *,
    normalized_value: float,
    age_hours: float,
    half_life_hours: float,
) -> SignalInput:
    dimension = DIMENSION_MAP.get(
        signal.signal_type.strip().lower()
    )

    if dimension is None:
        raise ValueError(
            f"Unsupported signal type: {signal.signal_type}"
        )

    return SignalInput(
        dimension=dimension,
        normalized_value=normalized_value,
        age_hours=age_hours,
        half_life_hours=half_life_hours,
        source=signal.source,
    )
