from dataclasses import dataclass


@dataclass(frozen=True)
class TrendResult:
    change: float
    direction: str


def calculate_trend(
    current_pulse: float,
    previous_pulse: float,
) -> TrendResult:
    if not 0.0 <= current_pulse <= 100.0:
        raise ValueError("current_pulse must be between 0 and 100")

    if not 0.0 <= previous_pulse <= 100.0:
        raise ValueError("previous_pulse must be between 0 and 100")

    change = round(current_pulse - previous_pulse, 2)

    if change > 0:
        direction = "up"
    elif change < 0:
        direction = "down"
    else:
        direction = "stable"

    return TrendResult(
        change=change,
        direction=direction,
    )
