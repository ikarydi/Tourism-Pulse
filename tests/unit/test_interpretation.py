import pytest

from tourism_pulse_api.pulse.calculator import PulseResult
from tourism_pulse_api.pulse.confidence import ConfidenceResult
from tourism_pulse_api.pulse.interpretation import interpret_pulse


def make_pulse(
    *,
    pulse: float = 60.0,
    demand: float = 60.0,
    capacity: float = 60.0,
    events: float = 60.0,
    environment: float = 60.0,
    risk: float = 60.0,
    economic: float = 60.0,
) -> PulseResult:
    return PulseResult(
        pulse=pulse,
        demand=demand,
        capacity=capacity,
        events=events,
        environment=environment,
        risk=risk,
        economic=economic,
    )


def make_confidence(
    *,
    score: float = 80.0,
    coverage: float = 100.0,
) -> ConfidenceResult:
    return ConfidenceResult(
        score=score,
        reliability=90.0,
        freshness=90.0,
        coverage=coverage,
    )


def test_strong_events_are_reported_as_strength() -> None:
    result = interpret_pulse(
        pulse=make_pulse(events=85.0),
        confidence=make_confidence(),
    )

    assert "Events are strong" in result["strengths"]


def test_weak_events_are_reported_as_weakness() -> None:
    result = interpret_pulse(
        pulse=make_pulse(events=25.0),
        confidence=make_confidence(),
    )

    assert "Events are weak" in result["weaknesses"]


def test_missing_events_are_reported() -> None:
    result = interpret_pulse(
        pulse=make_pulse(events=0.0),
        confidence=make_confidence(coverage=75.0),
    )

    assert "Events data is missing" in result["weaknesses"]


@pytest.mark.parametrize(
    ("pulse", "expected"),
    [
        (75.0, "Strong tourism activity"),
        (60.0, "Moderate tourism activity"),
        (40.0, "Moderate tourism activity"),
        # Regression: pulse scores below 40 (the frontend's own Weak/
        # Moderate/Strong cutoff - see lib/format.ts's scoreStatus())
        # used to fall into the same "Moderate ... based on available
        # data" wording as a pulse of 40, so a place shown with a "Weak"
        # badge could carry a headline calling it moderate.
        (20.0, "Weak tourism activity"),
        (0.0, "Weak tourism activity"),
    ],
)
def test_headline_reflects_pulse_level(
    pulse: float,
    expected: str,
) -> None:
    result = interpret_pulse(
        pulse=make_pulse(pulse=pulse),
        confidence=make_confidence(),
    )

    assert result["headline"] == expected


def test_partial_coverage_is_reported() -> None:
    result = interpret_pulse(
        pulse=make_pulse(),
        confidence=make_confidence(coverage=75.0),
    )

    assert result["data_quality"] == "partial"


def test_complete_coverage_is_reported() -> None:
    result = interpret_pulse(
        pulse=make_pulse(),
        confidence=make_confidence(coverage=100.0),
    )

    assert result["data_quality"] == "complete"
