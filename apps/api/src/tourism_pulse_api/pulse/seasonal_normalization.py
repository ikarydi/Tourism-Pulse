"""Seasonally-aware normalization for signals with a strong calendar pattern.

Tourism activity is highly seasonal - Budapest sees far more visitor-nights
in July than in January every single year - so comparing a raw monthly
figure against one fixed scale (as `normalize_min_max` or
`normalize_percentage` would) invents a false "high" or "low" reading purely
because of the time of year. Instead, each observation is compared against a
*seasonal baseline*: the average value recorded for the same calendar month
in prior years.

    ratio = current_value / seasonal_baseline

The ratio is then mapped into a bounded 0-1 score with a logistic ("sigmoid")
curve centered on ratio == 1.0, i.e. exactly average for the season:

    score = 1 / (1 + e^(-STEEPNESS * (ratio - 1)))

This transformation is:
  * deterministic - the same inputs always produce the same score.
  * bounded - the output always lies within [0, 1], and stays strictly
    between the two for any realistic ratio; only at extreme ratios (many
    multiples of the seasonal baseline) does floating-point precision round
    the result to exactly 0 or 1.
  * configurable - `steepness` controls how quickly the score saturates
    towards 0/1 as activity departs from the seasonal norm.
  * order preserving - ratio == 1.0 -> score == 0.5 exactly; ratio < 1.0
    (below-normal activity for the season) always scores below 0.5; ratio
    > 1.0 (above-normal activity) always scores above 0.5.

If there is not enough historical data for the same calendar month, the
baseline cannot be trusted, so `calculate_seasonal_score` reports an explicit
"insufficient_baseline" status instead of inventing a score from too little
data.
"""

import math
from dataclasses import dataclass

from tourism_pulse_api.pulse.normalization import clamp

# How quickly the score saturates towards 0/1 as the ratio departs from 1.0.
# At the default of 2.0: ratio 1.5 (50% above the seasonal norm) -> ~0.73,
# ratio 2.0 (double the seasonal norm) -> ~0.88, ratio 0.5 (half the norm)
# -> ~0.27.
DEFAULT_STEEPNESS = 2.0

# Minimum number of prior same-month observations required to trust a
# seasonal baseline. Below this, "insufficient_baseline" is reported.
DEFAULT_MIN_BASELINE_SAMPLES = 2

STATUS_OK = "ok"
STATUS_INSUFFICIENT_BASELINE = "insufficient_baseline"


@dataclass(frozen=True)
class SeasonalNormalizationResult:
    status: str  # STATUS_OK | STATUS_INSUFFICIENT_BASELINE
    score: float | None
    ratio: float | None
    baseline: float | None
    sample_size: int


def calculate_seasonal_baseline(
    historical_same_month_values: list[float],
    *,
    min_samples: int = DEFAULT_MIN_BASELINE_SAMPLES,
) -> float | None:
    """Average of prior same-calendar-month values, or None if too few exist."""
    if min_samples < 1:
        raise ValueError("min_samples must be at least 1")

    if len(historical_same_month_values) < min_samples:
        return None

    return sum(historical_same_month_values) / len(historical_same_month_values)


def seasonal_ratio_to_score(
    ratio: float,
    *,
    steepness: float = DEFAULT_STEEPNESS,
) -> float:
    """Map a current-value/seasonal-baseline ratio to a bounded 0-1 score.

    score = 1 / (1 + e^(-steepness * (ratio - 1)))
    """
    if steepness <= 0:
        raise ValueError("steepness must be greater than zero")

    if ratio < 0:
        raise ValueError("ratio cannot be negative")

    score = 1.0 / (1.0 + math.exp(-steepness * (ratio - 1.0)))

    # The sigmoid is already strictly within (0, 1); clamp defensively
    # against floating-point edge cases so the bound is never violated.
    return clamp(score)


def calculate_seasonal_score(
    current_value: float,
    historical_same_month_values: list[float],
    *,
    steepness: float = DEFAULT_STEEPNESS,
    min_samples: int = DEFAULT_MIN_BASELINE_SAMPLES,
) -> SeasonalNormalizationResult:
    """Seasonally normalize `current_value` against its calendar-month history.

    `historical_same_month_values` must already be filtered to the same
    calendar month as `current_value` (e.g. only prior Junes when normalizing
    a June observation) - this function does no date filtering itself.
    """
    if current_value < 0:
        raise ValueError("current_value cannot be negative")

    sample_size = len(historical_same_month_values)

    baseline = calculate_seasonal_baseline(
        historical_same_month_values,
        min_samples=min_samples,
    )

    if baseline is None or baseline == 0:
        # A zero baseline means there is no meaningful seasonal norm to
        # compare against (division would be undefined or unboundedly
        # "above normal") - treat it the same as an insufficient baseline
        # rather than inventing an extreme score.
        return SeasonalNormalizationResult(
            status=STATUS_INSUFFICIENT_BASELINE,
            score=None,
            ratio=None,
            baseline=baseline,
            sample_size=sample_size,
        )

    ratio = current_value / baseline
    score = seasonal_ratio_to_score(ratio, steepness=steepness)

    return SeasonalNormalizationResult(
        status=STATUS_OK,
        score=score,
        ratio=ratio,
        baseline=baseline,
        sample_size=sample_size,
    )
