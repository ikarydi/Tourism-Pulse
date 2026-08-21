from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.eurostat.parser import (
    EUROSTAT_SOURCE_NAME,
    NIGHTS_UNIT,
    latest_observation,
    parse_eurostat_tourism_nights,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eurostat_tour_occ_nim_sample.json"
)


@pytest.fixture()
def sample_response_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _make_response(*, geo_label: dict, time_index: dict, values: dict) -> str:
    import json

    return json.dumps(
        {
            "dimension": {
                "freq": {"category": {"index": {"M": 0}}},
                "c_resid": {"category": {"index": {"TOTAL": 0}}},
                "unit": {"category": {"index": {"NR": 0}}},
                "nace_r2": {"category": {"index": {"I551-I553": 0}}},
                "geo": {"category": {"index": {next(iter(geo_label)): 0}, "label": geo_label}},
                "time": {"category": {"index": time_index}},
            },
            "id": ["freq", "c_resid", "unit", "nace_r2", "geo", "time"],
            "size": [1, 1, 1, 1, 1, len(time_index)],
            "value": values,
        }
    )


def test_parses_all_published_months(sample_response_text: str) -> None:
    observations = parse_eurostat_tourism_nights(sample_response_text)

    assert len(observations) == 29


def test_geo_code_and_name_are_captured(sample_response_text: str) -> None:
    observations = parse_eurostat_tourism_nights(sample_response_text)

    assert all(o.geo == "AT" for o in observations)
    assert all(o.geo_name == "Austria" for o in observations)


def test_month_parsing_produces_correct_year_month_and_bounds(sample_response_text: str) -> None:
    observations = parse_eurostat_tourism_nights(sample_response_text)

    first = next(o for o in observations if o.period == "2024-01")

    assert first.year == 2024
    assert first.month == 1
    assert first.period_start.isoformat() == "2024-01-01"
    assert first.period_end.isoformat() == "2024-01-31"


def test_unit_is_raw_nights_not_thousands(sample_response_text: str) -> None:
    observations = parse_eurostat_tourism_nights(sample_response_text)

    assert all(o.unit == NIGHTS_UNIT for o in observations)


def test_observations_are_sorted_chronologically(sample_response_text: str) -> None:
    observations = parse_eurostat_tourism_nights(sample_response_text)

    periods = [(o.year, o.month) for o in observations]

    assert periods == sorted(periods)


def test_latest_observation_helper(sample_response_text: str) -> None:
    observations = parse_eurostat_tourism_nights(sample_response_text)

    assert latest_observation(observations).period == "2026-05"


def test_latest_observation_of_empty_list_is_none() -> None:
    assert latest_observation([]) is None


def test_empty_time_dimension_returns_empty_list() -> None:
    text = _make_response(geo_label={"AT": "Austria"}, time_index={}, values={})

    assert parse_eurostat_tourism_nights(text) == []


def test_unpublished_month_is_skipped_not_invented() -> None:
    text = _make_response(
        geo_label={"AT": "Austria"},
        time_index={"2026-01": 0, "2026-02": 1},
        values={"0": 100000},  # index 1 (2026-02) has no value yet
    )

    observations = parse_eurostat_tourism_nights(text)

    assert len(observations) == 1
    assert observations[0].period == "2026-01"


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_eurostat_tourism_nights("not json")


def test_error_response_raises_value_error() -> None:
    text = '{"error": [{"status": 400, "label": "INVALID_QUERY_DIMENSION"}]}'

    with pytest.raises(ValueError):
        parse_eurostat_tourism_nights(text)


def test_multiple_geo_categories_rejected() -> None:
    text = _make_response(
        geo_label={"AT": "Austria", "CZ": "Czechia"},
        time_index={"2026-01": 0},
        values={"0": 100000},
    )

    with pytest.raises(ValueError):
        parse_eurostat_tourism_nights(text)


def test_multivalued_non_time_dimension_rejected() -> None:
    import json

    text = json.dumps(
        {
            "dimension": {
                "freq": {"category": {"index": {"M": 0}}},
                "c_resid": {"category": {"index": {"TOTAL": 0}}},
                # unit has two categories - the flat-index assumption breaks.
                "unit": {"category": {"index": {"NR": 0, "PCH_SM": 1}}},
                "nace_r2": {"category": {"index": {"I551-I553": 0}}},
                "geo": {
                    "category": {"index": {"AT": 0}, "label": {"AT": "Austria"}}
                },
                "time": {"category": {"index": {"2026-01": 0}}},
            },
            "id": ["freq", "c_resid", "unit", "nace_r2", "geo", "time"],
            "size": [1, 1, 2, 1, 1, 1],
            "value": {"0": 100000},
        }
    )

    with pytest.raises(ValueError):
        parse_eurostat_tourism_nights(text)


def test_source_name_constant() -> None:
    assert EUROSTAT_SOURCE_NAME == "eurostat"


def test_greece_uses_el_not_gr_in_real_data() -> None:
    # Documents the real Eurostat geo-code gotcha (verified against the
    # live API): Greece is "EL", not the ISO code "GR".
    text = _make_response(
        geo_label={"EL": "Greece"},
        time_index={"2026-01": 0},
        values={"0": 1651344},
    )

    observations = parse_eurostat_tourism_nights(text)

    assert observations[0].geo == "EL"
    assert observations[0].geo_name == "Greece"
