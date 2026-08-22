"""Tests for turning a GDACS events observation into a
disaster_alert_severity Signal - the service layer's overwrite-in-place
idempotency, data-quality gating, lineage, and (the interesting part)
the inverted-polarity normalizer."""

from datetime import UTC, datetime

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.gdacs.parser import (
    GDACS_SOURCE_NAME,
    GdacsEvent,
    GdacsEventsObservation,
)
from tourism_pulse_api.ingestion.gdacs.service import (
    build_preview,
    upsert_disaster_alert_severity_signal,
)


def make_observation(
    max_score: float = 0.0,
    *,
    country: str = "HU",
    events: list[GdacsEvent] | None = None,
    retrieved_at: datetime = datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
) -> GdacsEventsObservation:
    return GdacsEventsObservation(
        country=country,
        events=events or [],
        max_current_alert_score=max_score,
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
    destination = Destination(country_code="HU", name="GDACS Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="GDACS Ingestion Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_build_preview_targets_the_risk_dimension() -> None:
    preview = build_preview(make_observation(2.0))

    assert preview.target_dimension == "risk"
    assert preview.max_current_alert_score == 2.0


def test_no_current_alerts_normalizes_to_full_safety() -> None:
    preview = build_preview(make_observation(0.0))

    assert preview.normalized_value == 1.0


def test_high_alert_score_normalizes_low_not_high() -> None:
    # The interesting/subtle part: unlike every other adapter, a HIGH raw
    # reading must produce a LOW normalized value (see
    # pulse.disaster_risk's docstring on Pulse dimension polarity).
    low_alert = build_preview(make_observation(1.0))
    high_alert = build_preview(make_observation(3.0))

    assert high_alert.normalized_value < low_alert.normalized_value
    assert high_alert.normalized_value == 0.0


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(2.0)

    signal, gate = upsert_disaster_alert_severity_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?country=HU",
    )

    assert gate.accepted is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "disaster_alert_severity"
    assert signal.value == 2.0
    assert signal.unit == "alert_score"
    assert signal.source == GDACS_SOURCE_NAME
    assert signal.observed_at == observation.retrieved_at


def test_upsert_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    first, _ = upsert_disaster_alert_severity_signal(
        db_session, place_id=test_place.id, observation=make_observation(1.0), source_url="https://a"
    )
    second, _ = upsert_disaster_alert_severity_signal(
        db_session, place_id=test_place.id, observation=make_observation(3.0), source_url="https://b"
    )

    assert first.id == second.id
    assert second.value == 3.0
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "disaster_alert_severity")
        .count()
        == 1
    )


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "gdacs").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="gdacs_events",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    signal, gate = upsert_disaster_alert_severity_signal(
        db_session,
        place_id=test_place.id,
        observation=make_observation(),
        source_url="https://a",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True
