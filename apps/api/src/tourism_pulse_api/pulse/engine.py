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
from tourism_pulse_api.pulse.normalization import clamp
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


# Tourism pressure (visitor load on residents and infrastructure) is
# reported next to the Pulse, never blended into it: for a hotel high
# demand is good news, for residents high pressure is the problem, so one
# "higher is better" composite cannot carry both. Higher pressure always
# means more strain.
PRESSURE_DIMENSION = "pressure"


@dataclass(frozen=True)
class EngineResult:
    pulse: PulseResult
    confidence: ConfidenceResult
    trend: TrendResult
    # 0-100, or None when the place has no pressure signals - never a
    # misleading 0.
    pressure: float | None = None


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
        pressure_signals = [
            signal for signal in signals if signal.dimension == PRESSURE_DIMENSION
        ]
        signals = [
            signal for signal in signals if signal.dimension != PRESSURE_DIMENSION
        ]

        if not signals:
            raise ValueError("At least one Pulse signal is required")

        dimension_values: dict[str, list[float]] = {
            "demand": [],
            "capacity": [],
            "events": [],
            "environment": [],
            "risk": [],
            "economic": [],
        }

        # Each signal's weight within its dimension is freshness *
        # reliability, so a dimension is the weighted *mean* of its
        # normalized values: sum(value * weight) / sum(weight). Dividing
        # by the weights (not just the reliabilities) is what keeps
        # staleness from dragging the reading itself toward zero - an old
        # KSH month still says what it said; it just counts for less
        # against fresher signals, and lowers confidence via
        # average_freshness below.
        dimension_weights: dict[str, list[float]] = {
            "demand": [],
            "capacity": [],
            "events": [],
            "environment": [],
            "risk": [],
            "economic": [],
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
            dimension_weights[signal.dimension].append(freshness * reliability)
            reliabilities.append(reliability)
            freshness_values.append(freshness)

        dimensions = {}

        for name, values in dimension_values.items():
            if not values:
                dimensions[name] = 0.0
                continue

            weight_total = sum(dimension_weights[name])

            dimensions[name] = (
                sum(values) / weight_total
                if weight_total
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
            # Spec 6.9: no history is "insufficient data", never "stable" -
            # the same term pulse.trend_analysis already uses.
            trend = TrendResult(
                change=0.0,
                direction="insufficient_data",
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
            pressure=self._pressure(pressure_signals),
        )

    def _pressure(self, signals: list[SignalInput]) -> float | None:
        """Same freshness * reliability weighted mean as a Pulse dimension."""
        weights = [
            calculate_freshness(signal.age_hours, signal.half_life_hours)
            * self._reliability_lookup(signal.source)
            for signal in signals
        ]
        weight_total = sum(weights)

        if not weight_total:
            return None

        value = sum(
            clamp(signal.normalized_value) * weight
            for signal, weight in zip(signals, weights, strict=True)
        ) / weight_total

        return round(value * 100, 2)
