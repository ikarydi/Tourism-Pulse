"""Tests for turning a YouTube search observation into a search_interest
Signal - the service layer's overwrite-in-place idempotency, data-quality
gating, and lineage."""

from datetime import UTC, datetime

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.youtube.parser import (
    YOUTUBE_SOURCE_NAME,
    YoutubeSearchObservation,
    YoutubeVideo,
)
from tourism_pulse_api.ingestion.youtube.service import (
    build_preview,
    upsert_search_interest_signal,
)


def make_observation(
    total_results: int = 18_400,
    *,
    query: str = "Budapest travel guide",
    retrieved_at: datetime = datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
    sample_video_titles: list[str] | None = None,
    videos: list[YoutubeVideo] | None = None,
) -> YoutubeSearchObservation:
    return YoutubeSearchObservation(
        query=query,
        total_results=total_results,
        retrieved_at=retrieved_at,
        sample_video_titles=sample_video_titles or ["Sample Video 1", "Sample Video 2"],
        videos=videos if videos is not None else [],
    )


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="YouTube Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="YouTube Ingestion Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_build_preview_targets_the_demand_dimension() -> None:
    preview = build_preview(make_observation())

    assert preview.target_dimension == "demand"
    assert preview.total_results == 18_400
    assert 0.0 < preview.normalized_value <= 1.0


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(18_400)

    signal, gate = upsert_search_interest_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://www.googleapis.com/youtube/v3/search?key=REDACTED&q=...",
    )

    assert gate.accepted is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "search_interest"
    assert signal.value == 18_400
    assert signal.unit == "count"
    assert signal.source == YOUTUBE_SOURCE_NAME
    assert signal.observed_at == observation.retrieved_at


def test_upsert_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    # Same reasoning as OSM's POI-count signal: a search-result count is
    # "the web as of now", not a period in a published series.
    first, _ = upsert_search_interest_signal(
        db_session, place_id=test_place.id, observation=make_observation(10_000), source_url="https://a"
    )
    second, _ = upsert_search_interest_signal(
        db_session, place_id=test_place.id, observation=make_observation(15_000), source_url="https://b"
    )

    assert first.id == second.id
    assert second.value == 15_000
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "search_interest")
        .count()
        == 1
    )


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "youtube").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="youtube_search",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    signal, gate = upsert_search_interest_signal(
        db_session,
        place_id=test_place.id,
        observation=make_observation(),
        source_url="https://a",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True


def test_upsert_rejects_negative_total_results(db_session, test_place) -> None:
    # parse_youtube_search itself already rejects a negative totalResults,
    # but the quality gate is a second, independent line of defense for
    # any candidate that reaches service.py by another path.
    observation = make_observation(-1)

    signal, gate = upsert_search_interest_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert signal is None
    assert gate.accepted is False
