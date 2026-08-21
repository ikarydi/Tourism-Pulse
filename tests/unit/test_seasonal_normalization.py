import pytest
from tourism_pulse_api.pulse.seasonal_normalization import (
    STATUS_INSUFFICIENT_BASELINE,
    STATUS_OK,
    calculate_seasonal_baseline,
    calculate_seasonal_score,
    seasonal_ratio_to_score,
)


def test_baseline_is_the_average_of_same_month_history() -> None:
    assert calculate_seasonal_baseline([100.0, 200.0, 300.0]) == 200.0


def test_baseline_insufficient_when_below_min_samples() -> None:
    assert calculate_seasonal_baseline([100.0], min_samples=2) is None


def test_baseline_min_samples_is_configurable() -> None:
    assert calculate_seasonal_baseline([100.0], min_samples=1) == 100.0


def test_baseline_rejects_non_positive_min_samples() -> None:
    with pytest.raises(ValueError):
        calculate_seasonal_baseline([100.0], min_samples=0)


def test_ratio_of_one_scores_exactly_half() -> None:
    assert seasonal_ratio_to_score(1.0) == 0.5


def test_ratio_below_one_scores_below_half() -> None:
    assert seasonal_ratio_to_score(0.5) < 0.5


def test_ratio_above_one_scores_above_half() -> None:
    assert seasonal_ratio_to_score(1.5) > 0.5


def test_score_stays_strictly_within_bounds_for_realistic_ratios() -> None:
    assert 0.0 < seasonal_ratio_to_score(0.01) < 1.0
    assert 0.0 < seasonal_ratio_to_score(10.0) < 1.0


def test_score_never_exceeds_bounds_even_for_absurdly_extreme_ratios() -> None:
    # Far beyond any plausible real-world ratio; floating-point precision
    # rounds this to exactly 1.0, which is still within [0, 1] - it must
    # never overshoot past 1.0.
    assert 0.0 <= seasonal_ratio_to_score(1000.0) <= 1.0


@pytest.mark.parametrize("ratio", [0.0, 0.1, 0.5, 1.0, 2.0, 10.0, 100.0])
def test_score_always_within_0_and_1(ratio: float) -> None:
    score = seasonal_ratio_to_score(ratio)

    assert 0.0 <= score <= 1.0


def test_negative_ratio_rejected() -> None:
    with pytest.raises(ValueError):
        seasonal_ratio_to_score(-1.0)


def test_non_positive_steepness_rejected() -> None:
    with pytest.raises(ValueError):
        seasonal_ratio_to_score(1.5, steepness=0)


def test_steepness_is_configurable() -> None:
    gentle = seasonal_ratio_to_score(1.5, steepness=1.0)
    steep = seasonal_ratio_to_score(1.5, steepness=5.0)

    assert steep > gentle > 0.5


def test_deterministic_same_inputs_produce_same_output() -> None:
    first = calculate_seasonal_score(150.0, [100.0, 100.0, 100.0])
    second = calculate_seasonal_score(150.0, [100.0, 100.0, 100.0])

    assert first == second


def test_calculate_seasonal_score_ok_status() -> None:
    result = calculate_seasonal_score(150.0, [100.0, 100.0, 100.0])

    assert result.status == STATUS_OK
    assert result.baseline == 100.0
    assert result.ratio == 1.5
    assert result.score is not None
    assert 0.0 < result.score < 1.0


def test_calculate_seasonal_score_insufficient_baseline() -> None:
    result = calculate_seasonal_score(150.0, [100.0])

    assert result.status == STATUS_INSUFFICIENT_BASELINE
    assert result.score is None
    assert result.ratio is None
    assert result.baseline is None


def test_calculate_seasonal_score_with_no_history_at_all() -> None:
    result = calculate_seasonal_score(150.0, [])

    assert result.status == STATUS_INSUFFICIENT_BASELINE
    assert result.sample_size == 0


def test_zero_baseline_is_treated_as_insufficient_not_divided_by_zero() -> None:
    result = calculate_seasonal_score(150.0, [0.0, 0.0])

    assert result.status == STATUS_INSUFFICIENT_BASELINE
    assert result.score is None


def test_negative_current_value_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_seasonal_score(-10.0, [100.0, 100.0])


def test_preserves_distinction_between_below_and_above_normal() -> None:
    below = calculate_seasonal_score(50.0, [100.0, 100.0])
    above = calculate_seasonal_score(150.0, [100.0, 100.0])

    assert below.score < 0.5 < above.score


def test_sample_size_is_always_reported() -> None:
    result = calculate_seasonal_score(150.0, [100.0, 110.0, 120.0])

    assert result.sample_size == 3
