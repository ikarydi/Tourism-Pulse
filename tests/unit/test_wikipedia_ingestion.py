"""Tests for turning a Wikipedia pageviews observation into a
wikipedia_pageviews Signal - the service layer's overwrite-in-place
idempotency, data-quality gating, and lineage."""

from datetime import UTC, datetime

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.wikipedia.parser import (
    WIKIPEDIA_SOURCE_NAME,
    WikipediaPageviewsObservation,
)
from tourism_pulse_api.ingestion.wikipedia.service import (
    build_preview,
    upsert_wikipedia_pageviews_signal,
)


def make_observation(
    total: int = 31_050,
    *,
    article: str = "Budapest",
    project: str = "en.wikipedia.org",
    retrieved_at: datetime = datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
    daily_views: list[int] | None = None,
) -> WikipediaPageviewsObservation:
    views = daily_views or [9800, 10200, 11050]
    return WikipediaPageviewsObservation(
        article=article,
        project=project,
        total_views=total if total is not None else sum(views),
        daily_views=views,
        retrieved_at=retrieved_at,
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
    destination = Destination(country_code="HU", name="Wikipedia Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Wikipedia Ingestion Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_build_preview_targets_the_demand_dimension() -> None:
    preview = build_preview(make_observation())

    assert preview.target_dimension == "demand"
    assert preview.total_views == 31_050
    assert 0.0 < preview.normalized_value <= 1.0


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(31_050)

    signal, gate = upsert_wikipedia_pageviews_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/...",
    )

    assert gate.accepted is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "wikipedia_pageviews"
    assert signal.value == 31_050
    assert signal.unit == "views"
    assert signal.source == WIKIPEDIA_SOURCE_NAME
    assert signal.observed_at == observation.retrieved_at


def test_upsert_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    first, _ = upsert_wikipedia_pageviews_signal(
        db_session, place_id=test_place.id, observation=make_observation(10_000), source_url="https://a"
    )
    second, _ = upsert_wikipedia_pageviews_signal(
        db_session, place_id=test_place.id, observation=make_observation(15_000), source_url="https://b"
    )

    assert first.id == second.id
    assert second.value == 15_000
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "wikipedia_pageviews")
        .count()
        == 1
    )


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "wikipedia").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="wikipedia_pageviews",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    signal, gate = upsert_wikipedia_pageviews_signal(
        db_session,
        place_id=test_place.id,
        observation=make_observation(),
        source_url="https://a",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True


def test_upsert_rejects_negative_total_views(db_session, test_place) -> None:
    # parse_wikipedia_pageviews itself already rejects a negative daily
    # count, but the quality gate is a second, independent line of
    # defense for any candidate that reaches service.py by another path.
    observation = make_observation(-1)

    signal, gate = upsert_wikipedia_pageviews_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert signal is None
    assert gate.accepted is False
