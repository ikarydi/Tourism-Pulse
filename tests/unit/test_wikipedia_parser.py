from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.wikipedia.parser import (
    WIKIPEDIA_SOURCE_NAME,
    parse_wikipedia_pageviews,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "wikipedia_pageviews_budapest_sample.json"
)


@pytest.fixture()
def sample_response_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parses_total_views(sample_response_text: str) -> None:
    observation = parse_wikipedia_pageviews(
        sample_response_text, article="Budapest", project="en.wikipedia.org"
    )

    assert observation.total_views == 9800 + 10200 + 11050


def test_parses_daily_views(sample_response_text: str) -> None:
    observation = parse_wikipedia_pageviews(
        sample_response_text, article="Budapest", project="en.wikipedia.org"
    )

    assert observation.daily_views == [9800, 10200, 11050]


def test_parses_article_and_project_verbatim(sample_response_text: str) -> None:
    observation = parse_wikipedia_pageviews(
        sample_response_text, article="Budapest", project="en.wikipedia.org"
    )

    assert observation.article == "Budapest"
    assert observation.project == "en.wikipedia.org"


def test_handles_empty_items_gracefully() -> None:
    observation = parse_wikipedia_pageviews(
        '{"items": []}', article="Nowhereville", project="en.wikipedia.org"
    )

    assert observation.total_views == 0
    assert observation.daily_views == []


def test_missing_items_defaults_to_empty() -> None:
    observation = parse_wikipedia_pageviews("{}", article="X", project="en.wikipedia.org")

    assert observation.total_views == 0


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_wikipedia_pageviews("not json", article="X", project="en.wikipedia.org")


def test_negative_views_raises_value_error() -> None:
    text = '{"items": [{"views": -5}]}'

    with pytest.raises(ValueError):
        parse_wikipedia_pageviews(text, article="X", project="en.wikipedia.org")


def test_source_name_constant() -> None:
    assert WIKIPEDIA_SOURCE_NAME == "wikipedia"
