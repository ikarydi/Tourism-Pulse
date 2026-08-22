from dataclasses import dataclass

from tourism_pulse_api.pulse.coefficients import (
    DIMENSION_WEIGHTS,
    validate_dimension_weights,
)


@dataclass(frozen=True)
class PulseResult:
    pulse: float
    demand: float
    capacity: float
    events: float
    environment: float
    risk: float
    economic: float


class PulseCalculator:
    def __init__(self) -> None:
        validate_dimension_weights()

    def calculate(
        self,
        *,
        demand: float,
        capacity: float,
        events: float,
        environment: float,
        risk: float,
        economic: float,
    ) -> PulseResult:
        dimensions = {
            "demand": demand,
            "capacity": capacity,
            "events": events,
            "environment": environment,
            "risk": risk,
            "economic": economic,
        }

        for name, value in dimensions.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0 and 1"
                )

        pulse = (
            demand * DIMENSION_WEIGHTS["demand"]
            + capacity * DIMENSION_WEIGHTS["capacity"]
            + events * DIMENSION_WEIGHTS["events"]
            + environment * DIMENSION_WEIGHTS["environment"]
            + risk * DIMENSION_WEIGHTS["risk"]
            + economic * DIMENSION_WEIGHTS["economic"]
        )

        return PulseResult(
            pulse=round(pulse * 100, 2),
            demand=round(demand * 100, 2),
            capacity=round(capacity * 100, 2),
            events=round(events * 100, 2),
            environment=round(environment * 100, 2),
            risk=round(risk * 100, 2),
            economic=round(economic * 100, 2),
        )

    def calculate_available(
        self,
        *,
        dimensions: dict[str, float],
    ) -> PulseResult:
        if not dimensions:
            raise ValueError("At least one dimension is required")

        for name, value in dimensions.items():
            if name not in DIMENSION_WEIGHTS:
                raise ValueError(f"Unknown dimension: {name}")

            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0 and 1"
                )

        total_weight = sum(
            DIMENSION_WEIGHTS[name]
            for name in dimensions
        )

        pulse = sum(
            value * DIMENSION_WEIGHTS[name]
            for name, value in dimensions.items()
        ) / total_weight

        return PulseResult(
            pulse=round(pulse * 100, 2),
            demand=round(dimensions.get("demand", 0.0) * 100, 2),
            capacity=round(dimensions.get("capacity", 0.0) * 100, 2),
            events=round(dimensions.get("events", 0.0) * 100, 2),
            environment=round(
                dimensions.get("environment", 0.0) * 100,
                2,
            ),
            risk=round(dimensions.get("risk", 0.0) * 100, 2),
            economic=round(dimensions.get("economic", 0.0) * 100, 2),
        )
