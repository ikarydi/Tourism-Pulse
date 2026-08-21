from datetime import UTC, datetime
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.gdelt.parser import (
    GDELT_SOURCE_NAME,
    parse_gdelt_artlist,
    parse_gdelt_timelinetone,
)

ARTLIST_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "gdelt_artlist_budapest_sample.json"
)
TIMELINETONE_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "gdelt_timelinetone_budapest_sample.json"
)


@pytest.fixture()
def artlist_response_text() -> str:
    return ARTLIST_FIXTURE.read_text(encoding="utf-8")


@pytest.fixture()
def timelinetone_response_text() -> str:
    return TIMELINETONE_FIXTURE.read_text(encoding="utf-8")


# --- ArtList ---------------------------------------------------------------


def test_parses_article_count(artlist_response_text: str) -> None:
    observation = parse_gdelt_artlist(artlist_response_text, query="Budapest tourism")

    assert observation.article_count == 3


def test_parses_query_verbatim(artlist_response_text: str) -> None:
    observation = parse_gdelt_artlist(artlist_response_text, query="Budapest tourism")

    assert observation.query == "Budapest tourism"


def test_parses_sample_article_titles(artlist_response_text: str) -> None:
    observation = parse_gdelt_artlist(artlist_response_text, query="Budapest tourism")

    assert observation.sample_article_titles == [
        "Egy felhavi magyar fizetesbe faj a kulfoldieknek a Sziget",
        "Budapest transit schedule changes for August 20th celebrations",
        "Budapest tourism numbers hit new record this summer",
    ]


def test_missing_articles_key_means_zero_results() -> None:
    observation = parse_gdelt_artlist("{}", query="obscure query with no coverage")

    assert observation.article_count == 0
    assert observation.sample_article_titles == []


def test_artlist_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_gdelt_artlist("not json", query="test")


def test_artlist_rate_limit_plaintext_response_raises_value_error() -> None:
    # GDELT returns a plaintext (non-JSON) message when rate-limited.
    text = "Please limit requests to one every 5 seconds"

    with pytest.raises(ValueError):
        parse_gdelt_artlist(text, query="test")


def test_artlist_malformed_article_raises_value_error() -> None:
    text = '{"articles": [{"no_title_field": true}]}'

    with pytest.raises(ValueError):
        parse_gdelt_artlist(text, query="test")


# --- TimelineTone ------------------------------------------------------


def test_parses_most_recent_tone(timelinetone_response_text: str) -> None:
    observation = parse_gdelt_timelinetone(timelinetone_response_text, query="Budapest tourism")

    assert observation.tone == 1.9


def test_parses_tone_observed_at(timelinetone_response_text: str) -> None:
    observation = parse_gdelt_timelinetone(timelinetone_response_text, query="Budapest tourism")

    assert observation.observed_at == datetime(2026, 8, 19, 0, 0, tzinfo=UTC)


def test_timelinetone_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_gdelt_timelinetone("not json", query="test")


def test_timelinetone_missing_timeline_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_gdelt_timelinetone("{}", query="test")


def test_timelinetone_empty_data_raises_value_error() -> None:
    text = '{"timeline": [{"data": []}]}'

    with pytest.raises(ValueError):
        parse_gdelt_timelinetone(text, query="test")


def test_source_name_constant() -> None:
    assert GDELT_SOURCE_NAME == "gdelt"
