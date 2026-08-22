from dataclasses import dataclass

from tourism_pulse_api.db.models.pulse_snapshot import PulseSnapshot


@dataclass(frozen=True)
class TrendAnalysisResult:
    current_pulse: float
    change_24h: float | None
    change_7d: float | None
    direction: str
    momentum: str
    positive_drivers: list[str]
    negative_drivers: list[str]


def _change(
    current: PulseSnapshot,
    previous: PulseSnapshot | None,
) -> float | None:
    if previous is None:
        return None

    return round(current.pulse - previous.pulse, 2)


def _direction(change: float | None) -> str:
    if change is None:
        return "insufficient_data"

    if change >= 2.0:
        return "up"

    if change <= -2.0:
        return "down"

    return "stable"


def _momentum(change: float | None) -> str:
    if change is None:
        return "unknown"

    absolute_change = abs(change)

    if absolute_change >= 10:
        return "strong"

    if absolute_change >= 5:
        return "moderate"

    return "weak"


def _drivers(
    current: PulseSnapshot,
    previous: PulseSnapshot | None,
) -> tuple[list[str], list[str]]:
    if previous is None:
        return [], []

    dimensions = {
        "Demand": current.demand - previous.demand,
        "Capacity": current.capacity - previous.capacity,
        "Events": current.events - previous.events,
        "Environment": current.environment - previous.environment,
        "Risk": current.risk - previous.risk,
        "Economic": current.economic - previous.economic,
    }

    positive = [
        f"{name} improved"
        for name, change in dimensions.items()
        if change >= 5
    ]

    negative = [
        f"{name} weakened"
        for name, change in dimensions.items()
        if change <= -5
    ]

    return positive, negative


def analyze_trend(
    *,
    current: PulseSnapshot,
    previous_24h: PulseSnapshot | None,
    previous_7d: PulseSnapshot | None,
) -> TrendAnalysisResult:
    change_24h = _change(current, previous_24h)
    change_7d = _change(current, previous_7d)

    primary_change = (
        change_24h
        if change_24h is not None
        else change_7d
    )

    positive_drivers, negative_drivers = _drivers(
        current,
        previous_24h or previous_7d,
    )

    return TrendAnalysisResult(
        current_pulse=current.pulse,
        change_24h=change_24h,
        change_7d=change_7d,
        direction=_direction(primary_change),
        momentum=_momentum(primary_change),
        positive_drivers=positive_drivers,
        negative_drivers=negative_drivers,
    )
