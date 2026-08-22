from collections.abc import Callable

from tourism_pulse_api.pulse.air_quality import normalize_pm25
from tourism_pulse_api.pulse.airport_traffic import normalize_airport_traffic
from tourism_pulse_api.pulse.disaster_risk import normalize_disaster_alert_severity
from tourism_pulse_api.pulse.economic_growth import normalize_turnover_growth
from tourism_pulse_api.pulse.news_category_mentions import normalize_news_category_mentions
from tourism_pulse_api.pulse.news_mentions import normalize_news_mentions
from tourism_pulse_api.pulse.news_sentiment import normalize_news_tone
from tourism_pulse_api.pulse.normalization import (
    normalize_percentage,
    normalize_sentiment,
)
from tourism_pulse_api.pulse.poi_density import (
    normalize_hotel_count,
    normalize_restaurant_count,
)
from tourism_pulse_api.pulse.search_interest import normalize_search_interest
from tourism_pulse_api.pulse.video_category_mentions import normalize_video_category_mentions
from tourism_pulse_api.pulse.visitor_pressure import normalize_visitor_pressure
from tourism_pulse_api.pulse.wikipedia_interest import normalize_wikipedia_pageviews

Normalizer = Callable[[float], float]


SIGNAL_NORMALIZERS: dict[str, Normalizer] = {
    "occupancy": normalize_percentage,
    "hotel_occupancy": normalize_percentage,
    "sentiment": normalize_sentiment,
    "weather_comfort": normalize_percentage,
    # Eurostat's net bed-place occupancy rate - already a bounded
    # percentage, so it needs no seasonal baseline (unlike tourism_nights).
    "occupancy_rate": normalize_percentage,
    # OSM POI counts - see pulse.poi_density for the saturating-log formula.
    "hotel_count": normalize_hotel_count,
    "restaurant_count": normalize_restaurant_count,
    # YouTube search-result counts - see pulse.search_interest.
    "search_interest": normalize_search_interest,
    # GDELT news coverage - see pulse.news_mentions / pulse.news_sentiment.
    "news_mentions": normalize_news_mentions,
    "news_sentiment": normalize_news_tone,
    # OpenSky airborne-aircraft count - see pulse.airport_traffic.
    "airport_traffic": normalize_airport_traffic,
    # Wikipedia 30-day pageview total - see pulse.wikipedia_interest.
    "wikipedia_pageviews": normalize_wikipedia_pageviews,
    # GDACS disaster-alert severity - see pulse.disaster_risk.
    "disaster_alert_severity": normalize_disaster_alert_severity,
    # OpenAQ PM2.5 reading - see pulse.air_quality.
    "air_quality_pm25": normalize_pm25,
    # Eurostat accommodation-sector turnover growth - see pulse.economic_growth.
    "tourism_turnover_growth": normalize_turnover_growth,
    # Derived tourism_nights / population ratio - see pulse.visitor_pressure.
    "visitor_pressure": normalize_visitor_pressure,
    # Per-category GDELT/YouTube item counts - see
    # pulse.news_category_mentions / pulse.video_category_mentions.
    "news_event_mentions": normalize_news_category_mentions,
    "news_risk_mentions": normalize_news_category_mentions,
    "news_economic_mentions": normalize_news_category_mentions,
    "video_event_mentions": normalize_video_category_mentions,
    "video_risk_mentions": normalize_video_category_mentions,
    "video_economic_mentions": normalize_video_category_mentions,
}


def normalize_signal(
    signal_type: str,
    value: float,
) -> float:
    normalized_type = signal_type.strip().lower()

    normalizer = SIGNAL_NORMALIZERS.get(normalized_type)

    if normalizer is None:
        raise ValueError(
            f"No normalizer configured for signal type: {signal_type}"
        )

    return normalizer(value)
