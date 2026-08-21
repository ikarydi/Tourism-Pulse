from datetime import UTC, datetime
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.events.parser import (
    TICKETMASTER_SOURCE_NAME,
    parse_ticketmaster_events,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ticketmaster_events_sample.json"
)


@pytest.fixture()
def sample_response_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parses_all_events_with_a_confirmed_date(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    # 5 events in the fixture, one (TBA Announcement Show) has no dateTime.
    assert len(events) == 4
    assert all(event.name != "TBA Announcement Show" for event in events)


def test_music_genre_festival_is_mapped_to_festival(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    festival = next(e for e in events if e.external_id == "vvG1zZbn23aAAo")

    assert festival.event_type == "festival"
    assert festival.name == "Budapest Summer Music Festival"


def test_sports_segment_is_mapped_to_sport(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    match = next(e for e in events if e.external_id == "G5vYZbW3nS9k1")

    assert match.event_type == "sport"


def test_arts_and_theatre_segment_is_mapped_to_cultural(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    ballet = next(e for e in events if e.external_id == "vv1tZbW3AeVzZ2")

    assert ballet.event_type == "cultural"


def test_miscellaneous_segment_is_mapped_to_other(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    fair = next(e for e in events if e.external_id == "vvXqZbW3nMisc1")

    assert fair.event_type == "other"


def test_start_and_end_datetimes_are_parsed_as_utc(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    festival = next(e for e in events if e.external_id == "vvG1zZbn23aAAo")

    assert festival.start_at == datetime(2026, 8, 28, 18, 0, tzinfo=UTC)
    assert festival.end_at == datetime(2026, 8, 30, 23, 0, tzinfo=UTC)


def test_missing_end_date_is_none_not_invented(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    match = next(e for e in events if e.external_id == "G5vYZbW3nS9k1")

    assert match.end_at is None


def test_venue_name_and_city_are_captured(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    festival = next(e for e in events if e.external_id == "vvG1zZbn23aAAo")

    assert festival.venue_name == "Danube Waterfront"
    assert festival.venue_city == "Budapest"


def test_event_with_no_venue_still_parses(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    fair = next(e for e in events if e.external_id == "vvXqZbW3nMisc1")

    assert fair.venue_city == "Budapest"


def test_source_url_is_captured(sample_response_text: str) -> None:
    events = parse_ticketmaster_events(sample_response_text)

    festival = next(e for e in events if e.external_id == "vvG1zZbn23aAAo")

    assert festival.source_url == "https://www.ticketmaster.com/event/vvG1zZbn23aAAo"


def test_empty_search_results_return_empty_list() -> None:
    text = '{"page": {"size": 50, "totalElements": 0, "totalPages": 0, "number": 0}}'

    assert parse_ticketmaster_events(text) == []


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_ticketmaster_events("not json")


def test_fault_response_raises_value_error() -> None:
    text = (
        '{"fault": {"faultstring": "Invalid ApiKey", '
        '"detail": {"errorcode": "oauth.v2.InvalidApiKey"}}}'
    )

    with pytest.raises(ValueError):
        parse_ticketmaster_events(text)


def test_source_name_constant() -> None:
    assert TICKETMASTER_SOURCE_NAME == "ticketmaster"
