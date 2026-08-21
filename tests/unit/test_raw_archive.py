"""Tests for the shared raw-archive (Bronze layer) helper."""

import hashlib
from datetime import UTC, datetime

import pytest
from tourism_pulse_api.db.models import Destination, Place, Source
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.raw_archive import (
    UnknownSourceError,
    archive_raw_observation,
)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def test_source(request, db_session) -> Source:
    # sources.name is globally unique and the test DB is shared across the
    # whole session (not reset per test) - derive the name from the test
    # function so parallel/successive tests never collide.
    unique_name = f"test_archive_source_{request.node.name}"
    source = Source(name=unique_name, category="commercial", reliability="0.900")
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="Raw Archive Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(destination_id=destination.id, name="Raw Archive Test Place", place_type="destination")
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


def test_archives_raw_payload_verbatim(db_session, test_source, test_place) -> None:
    payload = '{"total_results": 42}'

    observation = archive_raw_observation(
        db_session,
        source_name=test_source.name,
        dataset="test_dataset",
        raw_payload=payload,
        content_type="application/json",
        place_id=test_place.id,
        source_url="https://example.com/api?key=REDACTED",
    )

    assert observation.id is not None
    assert observation.source_id == test_source.id
    assert observation.dataset == "test_dataset"
    assert observation.place_id == test_place.id
    assert observation.raw_payload == payload
    assert observation.content_type == "application/json"


def test_checksum_is_sha256_of_payload(db_session, test_source) -> None:
    payload = "some,csv,data\n1,2,3"

    observation = archive_raw_observation(
        db_session,
        source_name=test_source.name,
        dataset="test_dataset",
        raw_payload=payload,
        content_type="text/csv",
    )

    assert observation.checksum == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_defaults_retrieved_at_to_now(db_session, test_source) -> None:
    before = datetime.now(UTC)

    observation = archive_raw_observation(
        db_session,
        source_name=test_source.name,
        dataset="test_dataset",
        raw_payload="{}",
        content_type="application/json",
    )

    after = datetime.now(UTC)

    assert before <= observation.retrieved_at <= after


def test_source_name_is_case_and_whitespace_insensitive(db_session, test_source) -> None:
    observation = archive_raw_observation(
        db_session,
        source_name=f"  {test_source.name.upper()}  ",
        dataset="test_dataset",
        raw_payload="{}",
        content_type="application/json",
    )

    assert observation.source_id == test_source.id


def test_unregistered_source_raises(db_session) -> None:
    with pytest.raises(UnknownSourceError):
        archive_raw_observation(
            db_session,
            source_name="totally_unregistered_source",
            dataset="test_dataset",
            raw_payload="{}",
            content_type="application/json",
        )
