"""Tests for turning an OpenSky airspace observation into an
airport_traffic Signal - overwrite-in-place idempotency, data-quality
gating, and lineage."""

from datetime import UTC, datetime

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.opensky.parser import (
    OPENSKY_SOURCE_NAME,
    OpenSkyAirspaceObservation,
)
from tourism_pulse_api.ingestion.opensky.service import (
    build_preview,
    upsert_airport_traffic_signal,
)


def make_observation(
    airborne_count: int = 12,
    *,
    retrieved_at: datetime = datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
    sample_callsigns: list[str] | None = None,
) -> OpenSkyAirspaceObservation:
    return OpenSkyAirspaceObservation(
        retrieved_at=retrieved_at,
        airborne_count=airborne_count,
        sample_callsigns=sample_callsigns or ["DLH123", "WZZ456"],
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
    destination = Destination(country_code="HU", name="OpenSky Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="OpenSky Ingestion Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_build_preview_targets_the_demand_dimension() -> None:
    preview = build_preview(make_observation())

    assert preview.target_dimension == "demand"
    assert preview.airborne_count == 12
    assert 0.0 < preview.normalized_value <= 1.0


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(12)

    signal, gate = upsert_airport_traffic_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://opensky-network.org/api/states/all?lamin=...",
    )

    assert gate.accepted is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "airport_traffic"
    assert signal.value == 12
    assert signal.unit == "count"
    assert signal.source == OPENSKY_SOURCE_NAME
    assert signal.observed_at == observation.retrieved_at


def test_upsert_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    first, _ = upsert_airport_traffic_signal(
        db_session, place_id=test_place.id, observation=make_observation(5), source_url="https://a"
    )
    second, _ = upsert_airport_traffic_signal(
        db_session, place_id=test_place.id, observation=make_observation(20), source_url="https://b"
    )

    assert first.id == second.id
    assert second.value == 20
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "airport_traffic")
        .count()
        == 1
    )


def test_upsert_zero_aircraft_is_valid(db_session, test_place) -> None:
    signal, gate = upsert_airport_traffic_signal(
        db_session, place_id=test_place.id, observation=make_observation(0), source_url="https://a"
    )

    assert gate.accepted is True
    assert signal.value == 0


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "opensky").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="opensky_states_all",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    signal, gate = upsert_airport_traffic_signal(
        db_session,
        place_id=test_place.id,
        observation=make_observation(),
        source_url="https://a",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True


def test_upsert_rejects_negative_count(db_session, test_place) -> None:
    signal, gate = upsert_airport_traffic_signal(
        db_session, place_id=test_place.id, observation=make_observation(-1), source_url="https://a"
    )

    assert signal is None
    assert gate.accepted is False
