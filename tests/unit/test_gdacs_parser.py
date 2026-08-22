from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.gdacs.parser import (
    GDACS_SOURCE_NAME,
    parse_gdacs_events,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "gdacs_events_hungary_sample.json"
)


@pytest.fixture()
def sample_response_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parses_events(sample_response_text: str) -> None:
    observation = parse_gdacs_events(sample_response_text, country="HU")

    assert len(observation.events) == 2
    assert observation.events[0].event_type == "DR"
    assert observation.events[0].alert_level == "Orange"


def test_max_current_alert_score_ignores_non_current_events(sample_response_text: str) -> None:
    # The fixture has one current Orange (score 2) event and one
    # non-current Green (score 1) event - only the current one counts.
    observation = parse_gdacs_events(sample_response_text, country="HU")

    assert observation.max_current_alert_score == 2.0


def test_country_is_recorded_verbatim(sample_response_text: str) -> None:
    observation = parse_gdacs_events(sample_response_text, country="HU")

    assert observation.country == "HU"


def test_handles_empty_features_gracefully() -> None:
    observation = parse_gdacs_events('{"type": "FeatureCollection", "features": []}', country="XX")

    assert observation.events == []
    assert observation.max_current_alert_score == 0.0


def test_missing_features_defaults_to_empty() -> None:
    observation = parse_gdacs_events("{}", country="HU")

    assert observation.max_current_alert_score == 0.0


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_gdacs_events("not json", country="HU")


def test_malformed_feature_raises_value_error() -> None:
    text = '{"features": [{"properties": {"eventtype": "DR"}}]}'

    with pytest.raises(ValueError):
        parse_gdacs_events(text, country="HU")


def test_source_name_constant() -> None:
    assert GDACS_SOURCE_NAME == "gdacs"
