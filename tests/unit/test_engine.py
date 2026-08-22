import pytest

from tourism_pulse_api.pulse.engine import (
    PulseEngine,
    SignalInput,
)


def make_signals() -> list[SignalInput]:
    return [
        SignalInput(
            dimension="demand",
            normalized_value=0.8,
            age_hours=0,
            half_life_hours=24,
            source="government",
        ),
        SignalInput(
            dimension="capacity",
            normalized_value=0.7,
            age_hours=2,
            half_life_hours=24,
            source="official",
        ),
        SignalInput(
            dimension="events",
            normalized_value=0.9,
            age_hours=1,
            half_life_hours=12,
            source="commercial",
        ),
        SignalInput(
            dimension="environment",
            normalized_value=0.85,
            age_hours=3,
            half_life_hours=24,
            source="government",
        ),
    ]


def test_engine_calculates_complete_result() -> None:
    engine = PulseEngine()

    result = engine.calculate(
        signals=make_signals(),
    )

    assert 0.0 <= result.pulse.pulse <= 100.0
    assert 0.0 <= result.confidence.score <= 100.0
    assert result.trend.change == 0.0
    assert result.trend.direction == "stable"


def test_engine_calculates_trend() -> None:
    engine = PulseEngine()

    result = engine.calculate(
        signals=make_signals(),
        previous_pulse=50.0,
    )

    assert result.trend.direction == "up"
    assert result.trend.change > 0


def test_engine_requires_signals() -> None:
    engine = PulseEngine()

    with pytest.raises(ValueError):
        engine.calculate(signals=[])


def test_engine_rejects_unknown_dimension() -> None:
    engine = PulseEngine()

    signals = [
        SignalInput(
            dimension="unknown",
            normalized_value=0.5,
            age_hours=0,
            half_life_hours=24,
            source="government",
        )
    ]

    with pytest.raises(ValueError):
        engine.calculate(signals=signals)


def test_engine_missing_dimensions_reduce_confidence() -> None:
    engine = PulseEngine()

    signals = [
        SignalInput(
            dimension="demand",
            normalized_value=0.8,
            age_hours=0,
            half_life_hours=24,
            source="government",
        )
    ]

    result = engine.calculate(signals=signals)

    assert result.pulse.capacity == 0.0
    assert result.pulse.events == 0.0
    assert result.pulse.environment == 0.0
    assert result.pulse.risk == 0.0
    assert result.pulse.economic == 0.0
    assert result.confidence.coverage == pytest.approx(
        100 / 6,
        abs=0.01,
    )

def test_engine_aggregates_multiple_signals_by_reliability() -> None:
    engine = PulseEngine()

    signals = [
        SignalInput(
            dimension="demand",
            normalized_value=0.9,
            age_hours=0,
            half_life_hours=24,
            source="government",
        ),
        SignalInput(
            dimension="demand",
            normalized_value=0.6,
            age_hours=0,
            half_life_hours=24,
            source="commercial",
        ),
    ]

    result = engine.calculate(signals=signals)

    assert result.pulse.demand == pytest.approx(75.79, abs=0.01)

    def test_engine_aggregates_multiple_signals_by_reliability() -> None:
        engine = PulseEngine()

        signals = [
            SignalInput(
                dimension="demand",
                normalized_value=0.9,
                age_hours=0,
                half_life_hours=24,
                source="government",
           ),
            SignalInput(
                dimension="demand",
                normalized_value=0.6,
                age_hours=0,
                half_life_hours=24,
                source="commercial",
            ),
        ]

    result = engine.calculate(signals=signals)

    assert result.pulse.demand == pytest.approx(75.79, abs=0.01)
