from decimal import Decimal
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.ksh_capacity.parser import (
    KSH_SOURCE_NAME,
    SUPPORTED_METRICS,
    latest_observation,
    parse_ksh_capacity_csv,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ksh_tur0071_sample.csv"
)


@pytest.fixture()
def sample_csv_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_default_metric_is_bed_places(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text)

    assert all(o.metric == "bed_places" for o in observations)
    assert all(o.unit == "beds" for o in observations)


def test_headline_june_2026_value(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text)

    june_2026 = next(o for o in observations if o.period == "2026-06")

    assert june_2026.value == Decimal(525300)
    assert june_2026.place_name == "Hungary"


def test_month_parsing_produces_correct_year_month_and_bounds(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text)

    june_2026 = next(o for o in observations if o.period == "2026-06")

    assert june_2026.year == 2026
    assert june_2026.month == 6
    assert june_2026.period_start.isoformat() == "2026-06-01"
    assert june_2026.period_end.isoformat() == "2026-06-30"


def test_unpublished_months_are_skipped_not_invented(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text)

    periods = {o.period for o in observations}

    assert "2026-07" not in periods
    assert "2026-08" not in periods


def test_year_over_year_percentage_row_is_not_parsed_as_an_observation(
    sample_csv_text: str,
) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text)

    june_2026_observations = [o for o in observations if o.period == "2026-06"]

    # Without the fix, the "Corresponding period of previous year = 100.0%"
    # row's comma-decimal percentage would either crash parsing or (worse)
    # silently coincide with being skipped only by luck of an unrelated
    # InvalidOperation - this asserts exactly one real June 2026 observation.
    assert len(june_2026_observations) == 1
    assert june_2026_observations[0].value == Decimal(525300)


def test_observations_are_sorted_chronologically(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text)

    periods = [(o.year, o.month) for o in observations]

    assert periods == sorted(periods)


def test_latest_observation_helper(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text)

    assert latest_observation(observations).period == "2026-06"


def test_latest_observation_of_empty_list_is_none() -> None:
    assert latest_observation([]) is None


def test_empty_csv_returns_empty_list() -> None:
    assert parse_ksh_capacity_csv("") == []


def test_source_name_constant() -> None:
    assert KSH_SOURCE_NAME == "ksh"


def test_supported_metrics() -> None:
    assert SUPPORTED_METRICS.keys() == {"units", "bedrooms", "bed_places"}


def test_units_metric_is_selectable_independently(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text, metric="units")

    june_2026 = next(o for o in observations if o.period == "2026-06")

    assert june_2026.metric == "units"
    assert june_2026.unit == "establishments"
    assert june_2026.value == Decimal(30215)


def test_bedrooms_metric_is_selectable_independently(sample_csv_text: str) -> None:
    observations = parse_ksh_capacity_csv(sample_csv_text, metric="bedrooms")

    june_2026 = next(o for o in observations if o.period == "2026-06")

    assert june_2026.metric == "bedrooms"
    assert june_2026.unit == "bedrooms"
    assert june_2026.value == Decimal(154920)


def test_unsupported_metric_raises() -> None:
    with pytest.raises(ValueError):
        parse_ksh_capacity_csv("irrelevant", metric="rooms_with_a_view")


def test_capacity_swings_strongly_with_season(sample_csv_text: str) -> None:
    # Confirms this table really does need seasonal normalization, not a
    # fixed scale - January capacity is a small fraction of June's.
    observations = parse_ksh_capacity_csv(sample_csv_text)

    january_2026 = next(o for o in observations if o.period == "2026-01")
    june_2026 = next(o for o in observations if o.period == "2026-06")

    assert january_2026.value < june_2026.value * Decimal("0.6")
