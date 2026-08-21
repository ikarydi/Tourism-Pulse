from dataclasses import dataclass


RELIABILITY_WEIGHT = 0.40
FRESHNESS_WEIGHT = 0.30
COVERAGE_WEIGHT = 0.30


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    reliability: float
    freshness: float
    coverage: float


def calculate_confidence(
    *,
    average_reliability: float,
    average_freshness: float,
    dimension_coverage: float,
) -> ConfidenceResult:
    values = {
        "average_reliability": average_reliability,
        "average_freshness": average_freshness,
        "dimension_coverage": dimension_coverage,
    }

    for name, value in values.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")

    score = (
        average_reliability * RELIABILITY_WEIGHT
        + average_freshness * FRESHNESS_WEIGHT
        + dimension_coverage * COVERAGE_WEIGHT
    )

    return ConfidenceResult(
        score=round(score * 100, 2),
        reliability=round(average_reliability * 100, 2),
        freshness=round(average_freshness * 100, 2),
        coverage=round(dimension_coverage * 100, 2),
    )
