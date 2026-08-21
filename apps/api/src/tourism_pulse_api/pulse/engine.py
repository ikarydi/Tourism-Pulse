from collections.abc import Callable
from dataclasses import dataclass

from tourism_pulse_api.pulse.calculator import PulseCalculator, PulseResult
from tourism_pulse_api.pulse.confidence import (
    ConfidenceResult,
    calculate_confidence,
)
from tourism_pulse_api.pulse.effective_signal import (
    calculate_effective_signal,
)
from tourism_pulse_api.pulse.freshness import calculate_freshness
from tourism_pulse_api.pulse.reliability import (
    get_source_reliability as get_dict_source_reliability,
)
from tourism_pulse_api.pulse.trend import TrendResult, calculate_trend


@dataclass(frozen=True)
class SignalInput:
    dimension: str
    normalized_value: float
    age_hours: float
    half_life_hours: float
    source: str


@dataclass(frozen=True)
class EngineResult:
    pulse: PulseResult
    confidence: ConfidenceResult
    trend: TrendResult


class PulseEngine:
    def __init__(
        self,
        reliability_lookup: Callable[[str], float] = get_dict_source_reliability,
    ) -> None:
        # Defaults to the dict-based lookup so the engine stays a pure,
        # DB-free class - its own unit tests construct SignalInput directly
        # and never touch a database. routers/pulse.py passes a
        # DB-backed lookup (pulse.source_registry.get_source_reliability,
        # partially applied with the request's Session) so production
        # reliability comes from the Source Registry instead.
        self.calculator = PulseCalculator()
        self._reliability_lookup = reliability_lookup

    def calculate(
        self,
        *,
        signals: list[SignalInput],
        previous_pulse: float | None = None,
    ) -> EngineResult:
        if not signals:
            raise ValueError("At least one signal is required")

        dimension_values: dict[str, list[float]] = {
            "demand": [],
            "capacity": [],
            "events": [],
            "environment": [],
        }

        dimension_reliabilities: dict[str, list[float]] = {
            "demand": [],
            "capacity": [],
            "events": [],
            "environment": [],
        }
        reliabilities: list[float] = []
        freshness_values: list[float] = []

        for signal in signals:
            if signal.dimension not in dimension_values:
                raise ValueError(
                    f"Unknown dimension: {signal.dimension}"
                )

            freshness = calculate_freshness(
                signal.age_hours,
                signal.half_life_hours,
            )

            reliability = self._reliability_lookup(signal.source)

            effective = calculate_effective_signal(
                signal.normalized_value,
                freshness,
                reliability,
            )

            dimension_values[signal.dimension].append(effective)
            dimension_reliabilities[signal.dimension].append(reliability)
            reliabilities.append(reliability)
            freshness_values.append(freshness)

        dimensions = {}

        for name, values in dimension_values.items():
            if not values:
                dimensions[name] = 0.0
                continue

            reliability_total = sum(
                dimension_reliabilities[name]
            )

            dimensions[name] = (
                sum(values) / reliability_total
                if reliability_total
                else 0.0
            )

        available_dimensions = {
            name: value
            for name, value in dimensions.items()
            if dimension_values[name]
        }

        pulse = self.calculator.calculate_available(
            dimensions=available_dimensions,
        )

        average_reliability = (
            sum(reliabilities) / len(reliabilities)
        )

        average_freshness = (
            sum(freshness_values) / len(freshness_values)
        )

        dimension_coverage = (
            sum(bool(values) for values in dimension_values.values())
            / len(dimension_values)
        )

        confidence = calculate_confidence(
            average_reliability=average_reliability,
            average_freshness=average_freshness,
            dimension_coverage=dimension_coverage,
        )

        if previous_pulse is None:
            trend = TrendResult(
                change=0.0,
                direction="stable",
            )
        else:
            trend = calculate_trend(
                current_pulse=pulse.pulse,
                previous_pulse=previous_pulse,
            )

        return EngineResult(
            pulse=pulse,
            confidence=confidence,
            trend=trend,
        )
