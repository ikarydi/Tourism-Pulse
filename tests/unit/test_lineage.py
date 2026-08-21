"""Tests for pulse.lineage.explain_signal - the Signal -> SourceObservation
-> Source (+ DataQualityResult) chain."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import SignalCandidate
from tourism_pulse_api.db.models import Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.pulse.lineage import SignalNotFoundError, explain_signal


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="Lineage Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Lineage Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


@pytest.fixture()
def test_source(request, db_session) -> Source:
    source = Source(
        name=f"test_lineage_source_{request.node.name}",
        category="commercial",
        reliability="0.900",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


def test_explain_signal_raises_for_missing_signal(db_session) -> None:
    with pytest.raises(SignalNotFoundError):
        explain_signal(db_session, 999_999_999)


def test_explain_signal_returns_empty_chain_for_manual_signal(db_session, test_place) -> None:
    # No source_observation_id set - the routers/signals.py manual POST path.
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

    chain = explain_signal(db_session, signal.id)

    assert chain.signal.id == signal.id
    assert chain.source_observation is None
    assert chain.source is None
    assert chain.quality_results == []


def test_explain_signal_walks_full_chain(db_session, test_place, test_source) -> None:
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

    chain = explain_signal(db_session, signal.id)

    assert chain.signal.id == signal.id
    assert chain.source_observation is not None
    assert chain.source_observation.id == observation.id
    assert chain.source is not None
    assert chain.source.id == test_source.id
    assert len(chain.quality_results) == 7
    assert all(r.source_observation_id == observation.id for r in chain.quality_results)
