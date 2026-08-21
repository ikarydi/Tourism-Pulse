def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(value, maximum))


def normalize_min_max(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")

    normalized = (value - minimum) / (maximum - minimum)

    return clamp(normalized)


def normalize_percentage(value: float) -> float:
    return clamp(value / 100.0)


def normalize_sentiment(value: float) -> float:
    if value < -1.0 or value > 1.0:
        raise ValueError("sentiment must be between -1 and 1")

    return (value + 1.0) / 2.0


def normalize_inverse(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")

    normalized = (maximum - value) / (maximum - minimum)

    return clamp(normalized)
def normalize_range(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    if maximum <= minimum:
        raise ValueError(
            "maximum must be greater than minimum"
        )

    normalized = (
        (value - minimum)
        / (maximum - minimum)
    )

    return clamp(normalized)
