from tourism_pulse_api.pulse.normalization import clamp


def calculate_effective_signal(
    normalized_value: float,
    freshness: float,
    reliability: float,
) -> float:
    normalized_value = clamp(normalized_value)
    freshness = clamp(freshness)
    reliability = clamp(reliability)

    return normalized_value * freshness * reliability
