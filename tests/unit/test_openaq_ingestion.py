"""Tests for turning an OpenAQ PM2.5 observation into an air_quality_pm25
Signal - the service layer's overwrite-in-place idempotency, data-quality
gating, and lineage."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal, Source
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.openaq.parser import (
    OPENAQ_SOURCE_NAME,
    AirQualityObservation,
)
from tourism_pulse_api.ingestion.openaq.service import (
    build_preview,
    upsert_air_quality_signal,
)


def make_observation(
    value: float = 14.6,
    *,
    location_name: str = "Budapest Kozponti",
    unit: str = "µg/m³",
    retrieved_at: datetime = datetime(2026, 8, 21, 9, 0, tzinfo=UTC),
) -> AirQualityObservation:
    return AirQualityObservation(
        location_id=8901,
        location_name=location_name,
        sensor_id=55001,
        pm25_value=value,
        pm25_unit=unit,
        observed_at=retrieved_at,
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
    destination = Destination(country_code="HU", name="OpenAQ Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="OpenAQ Ingestion Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_build_preview_targets_the_environment_dimension() -> None:
    preview = build_preview(make_observation())

    assert preview.target_dimension == "environment"
    assert preview.pm25_value == 14.6


def test_good_air_quality_normalizes_to_full_marks() -> None:
    preview = build_preview(make_observation(5.0))

    assert preview.normalized_value == 1.0


def test_unhealthy_air_quality_normalizes_low_not_high() -> None:
    # Inverted polarity, same as pulse.disaster_risk: a HIGH PM2.5
    # reading (worse air) must produce a LOW normalized value.
    good = build_preview(make_observation(5.0))
    unhealthy = build_preview(make_observation(80.0))

    assert unhealthy.normalized_value < good.normalized_value
    assert unhealthy.normalized_value == 0.0


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(14.6)

    signal, gate = upsert_air_quality_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://api.openaq.org/v3/locations/8901/latest",
    )

    assert gate.accepted is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "air_quality_pm25"
    assert signal.value == Decimal("14.6")
    assert signal.unit == "µg/m³"
    assert signal.source == OPENAQ_SOURCE_NAME
    assert signal.observed_at == observation.observed_at


def test_upsert_overwrites_rather_than_accumulates(db_session, test_place) -> None:
    first, _ = upsert_air_quality_signal(
        db_session, place_id=test_place.id, observation=make_observation(10.0), source_url="https://a"
    )
    second, _ = upsert_air_quality_signal(
        db_session, place_id=test_place.id, observation=make_observation(20.0), source_url="https://b"
    )

    assert first.id == second.id
    assert second.value == 20.0
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "air_quality_pm25")
        .count()
        == 1
    )


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "openaq").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="openaq_latest",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    signal, gate = upsert_air_quality_signal(
        db_session,
        place_id=test_place.id,
        observation=make_observation(),
        source_url="https://a",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True


def test_upsert_rejects_negative_pm25_value(db_session, test_place) -> None:
    # parse_openaq_latest itself already rejects a negative value, but
    # the quality gate is a second, independent line of defense for any
    # candidate that reaches service.py by another path.
    observation = make_observation(-1.0)

    signal, gate = upsert_air_quality_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert signal is None
    assert gate.accepted is False
