from datetime import UTC, datetime
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.opensky.parser import (
    OPENSKY_SOURCE_NAME,
    parse_opensky_states,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "opensky_states_budapest_sample.json"
)


@pytest.fixture()
def sample_response_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_counts_only_airborne_aircraft(sample_response_text: str) -> None:
    observation = parse_opensky_states(sample_response_text)

    # 4 states in the fixture, 1 on_ground=true - excluded.
    assert observation.airborne_count == 3


def test_retrieved_at_from_response_time(sample_response_text: str) -> None:
    observation = parse_opensky_states(sample_response_text)

    assert observation.retrieved_at == datetime.fromtimestamp(1755772800, tz=UTC)


def test_sample_callsigns_are_stripped_and_exclude_blank(sample_response_text: str) -> None:
    observation = parse_opensky_states(sample_response_text)

    assert observation.sample_callsigns == ["DLH123", "WZZ456", "AUA789"]


def test_null_states_means_empty_airspace() -> None:
    text = '{"time": 1755772800, "states": null}'

    observation = parse_opensky_states(text)

    assert observation.airborne_count == 0
    assert observation.sample_callsigns == []


def test_missing_states_key_means_empty_airspace() -> None:
    text = '{"time": 1755772800}'

    observation = parse_opensky_states(text)

    assert observation.airborne_count == 0


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_opensky_states("not json")


def test_missing_time_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_opensky_states('{"states": []}')


def test_malformed_state_vector_raises_value_error() -> None:
    text = '{"time": 1755772800, "states": [["too", "short"]]}'

    with pytest.raises(ValueError):
        parse_opensky_states(text)


def test_source_name_constant() -> None:
    assert OPENSKY_SOURCE_NAME == "opensky"
