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
    assert result.trend.direction == "insufficient_data"


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


def test_stale_signal_keeps_its_level() -> None:
    # A lone monthly statistic two half-lives old must still read at its
    # own level - staleness lowers confidence, not the reading.
    engine = PulseEngine()

    result = engine.calculate(
        signals=[
            SignalInput(
                dimension="demand",
                normalized_value=0.6,
                age_hours=1440,
                half_life_hours=720,
                source="government",
            )
        ]
    )

    assert result.pulse.demand == pytest.approx(60.0)
    assert result.confidence.freshness == pytest.approx(25.0)


def test_fresher_signal_outweighs_stale_one_in_same_dimension() -> None:
    engine = PulseEngine()

    result = engine.calculate(
        signals=[
            SignalInput(
                dimension="demand",
                normalized_value=0.2,
                age_hours=0,
                half_life_hours=24,
                source="government",
            ),
            SignalInput(
                dimension="demand",
                normalized_value=0.8,
                age_hours=24,
                half_life_hours=24,
                source="government",
            ),
        ]
    )

    # weights 1.0 and 0.5 -> (0.2 * 1.0 + 0.8 * 0.5) / 1.5 = 0.4
    assert result.pulse.demand == pytest.approx(40.0)


def test_pressure_is_reported_beside_the_pulse_not_inside_it() -> None:
    engine = PulseEngine()
    demand = SignalInput(
        dimension="demand",
        normalized_value=0.5,
        age_hours=0,
        half_life_hours=24,
        source="government",
    )

    without_pressure = engine.calculate(signals=[demand])
    with_pressure = engine.calculate(
        signals=[
            demand,
            SignalInput(
                dimension="pressure",
                normalized_value=0.9,
                age_hours=0,
                half_life_hours=720,
                source="government",
            ),
        ]
    )

    assert without_pressure.pressure is None
    assert with_pressure.pressure == pytest.approx(90.0)
    # Pressure changes neither the composite, any dimension, nor confidence.
    assert with_pressure.pulse == without_pressure.pulse
    assert with_pressure.confidence == without_pressure.confidence


def test_pressure_signals_alone_cannot_produce_a_pulse() -> None:
    engine = PulseEngine()

    with pytest.raises(ValueError):
        engine.calculate(
            signals=[
                SignalInput(
                    dimension="pressure",
                    normalized_value=0.9,
                    age_hours=0,
                    half_life_hours=720,
                    source="government",
                )
            ]
        )
