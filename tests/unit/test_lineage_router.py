"""Tests for GET /places/{place_id}/signals/{signal_id}/lineage and
/events/{event_id}/lineage - the first HTTP callers of
pulse.lineage.explain_signal/explain_event."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import SignalCandidate
from tourism_pulse_api.db.models import Destination, Event, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.main import app

client = TestClient(app)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="Lineage Router Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Lineage Router Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


@pytest.fixture()
def other_place(db_session, test_place) -> Place:
    place = Place(
        destination_id=test_place.destination_id,
        name="Some Other Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


@pytest.fixture()
def test_source(request, db_session) -> Source:
    source = Source(
        name=f"lineage_router_test_source_{request.node.name}",
        category="commercial",
        reliability="0.900",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


def test_signal_place_not_found_returns_404() -> None:
    response = client.get("/places/999999999/signals/1/lineage")

    assert response.status_code == 404


def test_signal_not_found_returns_404(test_place) -> None:
    response = client.get(f"/places/{test_place.id}/signals/999999999/lineage")

    assert response.status_code == 404


def test_signal_from_a_different_place_returns_404(db_session, test_place, other_place) -> None:
    signal = Signal(
        place_id=other_place.id,
        signal_type="weather_comfort",
        value=Decimal("50"),
        unit="score",
        observed_at=datetime.now(UTC),
        source="government",
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    response = client.get(f"/places/{test_place.id}/signals/{signal.id}/lineage")

    assert response.status_code == 404


def test_signal_lineage_walks_full_chain(db_session, test_place, test_source) -> None:
    observation = SourceObservation(
        source_id=test_source.id,
        dataset="test_dataset",
        place_id=test_place.id,
        retrieved_at=datetime.now(UTC),
        raw_payload='{"value": 50}',
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation)
    db_session.commit()
    db_session.refresh(observation)

    candidate = SignalCandidate(
        place_id=test_place.id,
        signal_type="weather_comfort",
        value=Decimal("50"),
        unit="score",
        observed_at=datetime.now(UTC),
        source=test_source.name,
        source_observation_id=observation.id,
    )
    gate = run_quality_checks(db_session, candidate)
    assert gate.accepted is True

    signal = Signal(
        place_id=test_place.id,
        signal_type=candidate.signal_type,
        value=candidate.value,
        unit=candidate.unit,
        observed_at=candidate.observed_at,
        source=candidate.source,
        source_observation_id=observation.id,
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    response = client.get(f"/places/{test_place.id}/signals/{signal.id}/lineage")

    assert response.status_code == 200
    body = response.json()
    assert body["signal_id"] == signal.id
    assert body["signal_type"] == "weather_comfort"
    assert body["source_observation"]["id"] == observation.id
    assert body["source_detail"]["id"] == test_source.id
    assert len(body["quality_results"]) == 7


def test_signal_lineage_handles_manual_signal_with_no_observation(db_session, test_place) -> None:
    signal = Signal(
        place_id=test_place.id,
        signal_type="weather_comfort",
        value=Decimal("50"),
        unit="score",
        observed_at=datetime.now(UTC),
        source="government",
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    response = client.get(f"/places/{test_place.id}/signals/{signal.id}/lineage")

    assert response.status_code == 200
    body = response.json()
    assert body["source_observation"] is None
    assert body["source_detail"] is None
    assert body["quality_results"] == []


def test_event_not_found_returns_404(test_place) -> None:
    response = client.get(f"/places/{test_place.id}/events/999999999/lineage")

    assert response.status_code == 404


def test_event_lineage_handles_manual_event_with_no_observation(db_session, test_place) -> None:
    event = Event(
        place_id=test_place.id,
        name="Manual Event",
        event_type="other",
        start_at=datetime.now(UTC),
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    response = client.get(f"/places/{test_place.id}/events/{event.id}/lineage")

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == event.id
    assert body["source_observation"] is None
