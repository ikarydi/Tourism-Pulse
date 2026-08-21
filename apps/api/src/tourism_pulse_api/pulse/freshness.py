import math


def calculate_freshness(
    age_hours: float,
    half_life_hours: float,
) -> float:
    if age_hours < 0:
        raise ValueError("age_hours cannot be negative")

    if half_life_hours <= 0:
        raise ValueError("half_life_hours must be greater than zero")

    return math.pow(0.5, age_hours / half_life_hours)

