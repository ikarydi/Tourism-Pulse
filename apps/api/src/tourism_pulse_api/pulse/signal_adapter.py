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
