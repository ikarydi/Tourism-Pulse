from datetime import UTC, datetime

from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.pulse.engine import SignalInput
from tourism_pulse_api.pulse.signal_adapter import signal_to_input
from tourism_pulse_api.pulse.signal_normalization import normalize_signal

DEFAULT_HALF_LIFE_HOURS: dict[str, float] = {
    "demand": 24.0,
    "capacity": 48.0,
    "occupancy": 24.0,
    "hotel_occupancy": 24.0,
    "event": 12.0,
    "events": 12.0,
    "environment": 6.0,
    "sentiment": 12.0,
    "weather_comfort": 6.0,
    # KSH publishes tourism_nights and accommodation_capacity monthly, not in
    # real time - a ~30 day half-life keeps them from being treated as stale
    # the way a same-day signal type would be after a few hours.
    "tourism_nights": 720.0,
    "accommodation_capacity": 720.0,
    # Eurostat's occupancy rate is also monthly.
    "occupancy_rate": 720.0,
    # Eurostat's tour_cap_nat (bed-places) is published annually, not
    # monthly - a distinct signal_type from KSH's accommodation_capacity so
    # it can carry its own half-life. Using the 720h monthly half-life here
    # would decay a still-fully-valid annual figure to near-zero within a
    # couple of months of publication. ~365 days mirrors the same
    # "half-life ~= publish cadence" reasoning as the monthly ones above.
    "accommodation_capacity_annual": 8760.0,
    # OSM POI counts (hotels, restaurants) have no publish cadence of their
    # own - the map is continuously edited, but we only periodically
    # re-scrape it. ~90 days assumes a roughly quarterly re-ingestion
    # cadence; a count doesn't become meaningfully wrong faster than that.
    "hotel_count": 2160.0,
    "restaurant_count": 2160.0,
}


def calculate_age_hours(
    observed_at: datetime,
    *,
    now: datetime | None = None,
) -> float:
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    if now is None:
        now = datetime.now(UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    age_hours = (
        now - observed_at
    ).total_seconds() / 3600

    if age_hours < 0:
        return 0.0

    return age_hours


def get_half_life_hours(signal_type: str) -> float:
    normalized_type = signal_type.strip().lower()

    try:
        return DEFAULT_HALF_LIFE_HOURS[normalized_type]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported signal type: {signal_type}"
        ) from exc


def process_signal(
    signal: Signal,
    *,
    now: datetime | None = None,
) -> SignalInput:
    age_hours = calculate_age_hours(
        signal.observed_at,
        now=now,
    )

    half_life_hours = get_half_life_hours(
        signal.signal_type,
    )

    normalized_value = normalize_signal(
        signal.signal_type,
        float(signal.value),
    )

    return signal_to_input(
        signal,
        normalized_value=normalized_value,
        age_hours=age_hours,
        half_life_hours=half_life_hours,
    )
