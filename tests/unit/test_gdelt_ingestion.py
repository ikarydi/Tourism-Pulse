"""Tests for turning GDELT observations into Signal rows - overwrite-in-
place idempotency, data-quality gating, and lineage, for both signal
types."""

from datetime import UTC, datetime

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.gdelt.parser import (
    GDELT_SOURCE_NAME,
    GdeltArticleListObservation,
    GdeltToneObservation,
)
from tourism_pulse_api.ingestion.gdelt.service import (
    build_mentions_preview,
    build_tone_preview,
    upsert_news_mentions_signal,
    upsert_news_sentiment_signal,
)


def make_mentions_observation(
    article_count: int = 42,
    *,
    query: str = "Budapest tourism",
    retrieved_at: datetime = datetime(2026, 8, 19, 10, 0, tzinfo=UTC),
    sample_article_titles: list[str] | None = None,
) -> GdeltArticleListObservation:
    return GdeltArticleListObservation(
        query=query,
        article_count=article_count,
        retrieved_at=retrieved_at,
        sample_article_titles=sample_article_titles or ["Sample Article 1", "Sample Article 2"],
    )


def make_tone_observation(
    tone: float = 1.9,
    *,
    query: str = "Budapest tourism",
    observed_at: datetime = datetime(2026, 8, 19, 0, 0, tzinfo=UTC),
) -> GdeltToneObservation:
    return GdeltToneObservation(query=query, tone=tone, observed_at=observed_at)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="GDELT Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="GDELT Ingestion Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


# --- news_mentions ----------------------------------------------------


def test_build_mentions_preview_targets_the_demand_dimension() -> None:
    preview = build_mentions_preview(make_mentions_observation())

    assert preview.target_dimension == "demand"
    assert preview.article_count == 42
    assert 0.0 < preview.normalized_value <= 1.0


def test_upsert_mentions_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_mentions_observation(42)

    signal, gate = upsert_news_mentions_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://api.gdeltproject.org/api/v2/doc/doc?query=...",
    )

    assert gate.accepted is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "news_mentions"
    assert signal.value == 42
    assert signal.unit == "count"
    assert signal.source == GDELT_SOURCE_NAME
    assert signal.observed_at == observation.retrieved_at


def test_upsert_mentions_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    first, _ = upsert_news_mentions_signal(
        db_session, place_id=test_place.id, observation=make_mentions_observation(10), source_url="https://a"
    )
    second, _ = upsert_news_mentions_signal(
        db_session, place_id=test_place.id, observation=make_mentions_observation(15), source_url="https://b"
    )

    assert first.id == second.id
    assert second.value == 15
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "news_mentions")
        .count()
        == 1
    )


def test_upsert_mentions_zero_results_is_valid(db_session, test_place) -> None:
    signal, gate = upsert_news_mentions_signal(
        db_session, place_id=test_place.id, observation=make_mentions_observation(0), source_url="https://a"
    )

    assert gate.accepted is True
    assert signal.value == 0


# --- news_sentiment -----------------------------------------------------


def test_build_tone_preview_targets_the_demand_dimension() -> None:
    preview = build_tone_preview(make_tone_observation())

    assert preview.target_dimension == "demand"
    assert preview.tone == 1.9
    assert 0.0 <= preview.normalized_value <= 1.0


def test_upsert_sentiment_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_tone_observation(1.9)

    signal, gate = upsert_news_sentiment_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://api.gdeltproject.org/api/v2/doc/doc?query=...",
    )

    assert gate.accepted is True
    assert signal.signal_type == "news_sentiment"
    assert float(signal.value) == pytest.approx(1.9)
    assert signal.unit == "tone"
    assert signal.observed_at == observation.observed_at


def test_upsert_sentiment_rejects_out_of_range_tone(db_session, test_place) -> None:
    # GDELT's documented theoretical range is [-100, 100] - anything
    # further out signals a parsing/unit bug, not real coverage.
    observation = make_tone_observation(500.0)

    signal, gate = upsert_news_sentiment_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert signal is None
    assert gate.accepted is False


def test_upsert_sentiment_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    first, _ = upsert_news_sentiment_signal(
        db_session, place_id=test_place.id, observation=make_tone_observation(1.0), source_url="https://a"
    )
    second, _ = upsert_news_sentiment_signal(
        db_session, place_id=test_place.id, observation=make_tone_observation(-2.0), source_url="https://b"
    )

    assert first.id == second.id
    assert float(second.value) == pytest.approx(-2.0)
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "news_sentiment")
        .count()
        == 1
    )


# --- lineage --------------------------------------------------------------


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "gdelt").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="gdelt_doc_artlist",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    signal, gate = upsert_news_mentions_signal(
        db_session,
        place_id=test_place.id,
        observation=make_mentions_observation(),
        source_url="https://a",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True
