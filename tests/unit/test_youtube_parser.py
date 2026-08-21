from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.youtube.parser import (
    YOUTUBE_SOURCE_NAME,
    parse_youtube_search,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "youtube_search_budapest_sample.json"
)


@pytest.fixture()
def sample_response_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parses_total_results(sample_response_text: str) -> None:
    observation = parse_youtube_search(sample_response_text, query="Budapest travel guide")

    assert observation.total_results == 18400


def test_parses_query_verbatim(sample_response_text: str) -> None:
    observation = parse_youtube_search(sample_response_text, query="Budapest travel guide")

    assert observation.query == "Budapest travel guide"


def test_parses_sample_video_titles(sample_response_text: str) -> None:
    observation = parse_youtube_search(sample_response_text, query="Budapest travel guide")

    assert observation.sample_video_titles == [
        "Budapest Travel Guide 2026 - Top 10 Things to Do",
        "48 Hours in Budapest - Complete Itinerary",
        "Budapest Thermal Baths You Must Visit",
    ]


def test_handles_missing_items_gracefully() -> None:
    text = '{"pageInfo": {"totalResults": 500}}'

    observation = parse_youtube_search(text, query="test")

    assert observation.total_results == 500
    assert observation.sample_video_titles == []


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_youtube_search("not json", query="test")


def test_missing_page_info_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_youtube_search('{"items": []}', query="test")


def test_negative_total_results_raises_value_error() -> None:
    text = '{"pageInfo": {"totalResults": -1}}'

    with pytest.raises(ValueError):
        parse_youtube_search(text, query="test")


def test_source_name_constant() -> None:
    assert YOUTUBE_SOURCE_NAME == "youtube"
