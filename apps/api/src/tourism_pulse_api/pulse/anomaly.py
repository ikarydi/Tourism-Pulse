from dataclasses import dataclass

from tourism_pulse_api.db.models.pulse_snapshot import PulseSnapshot


@dataclass(frozen=True)
class AnomalyResult:
    detected: bool
    severity: str
    change: float | None
    message: str
    drivers: list[str]


def _severity(
    change: float,
    confidence_score: float,
) -> str:
    magnitude = abs(change)

    if confidence_score < 50:
        return "low"

    if magnitude >= 20:
        return "extreme"

    if magnitude >= 10:
        return "high"

    if magnitude >= 5:
        return "moderate"

    return "low"


def _drivers(
    current: PulseSnapshot,
    previous: PulseSnapshot,
) -> list[str]:
    dimensions = {
        "Demand": current.demand - previous.demand,
        "Capacity": current.capacity - previous.capacity,
        "Events": current.events - previous.events,
        "Environment": current.environment - previous.environment,
        "Risk": current.risk - previous.risk,
        "Economic": current.economic - previous.economic,
    }

    return [
        f"{name} changed by {change:+.1f}"
        for name, change in dimensions.items()
        if abs(change) >= 5
    ]


def detect_anomaly(
    *,
    current: PulseSnapshot,
    previous: PulseSnapshot | None,
) -> AnomalyResult:
    if previous is None:
        return AnomalyResult(
            detected=False,
            severity="none",
            change=None,
            message="Insufficient history to detect an anomaly",
            drivers=[],
        )

    change = round(current.pulse - previous.pulse, 2)

    if abs(change) < 5:
        return AnomalyResult(
            detected=False,
            severity="none",
            change=change,
            message="Pulse movement is within the normal range",
            drivers=[],
        )

    severity = _severity(
        change,
        current.confidence_score,
    )

    direction = "increased" if change > 0 else "decreased"

    return AnomalyResult(
        detected=True,
        severity=severity,
        change=change,
        message=(
            f"Tourism Pulse {direction} by "
            f"{abs(change):.1f} points"
        ),
        drivers=_drivers(
            current,
            previous,
        ),
    )
