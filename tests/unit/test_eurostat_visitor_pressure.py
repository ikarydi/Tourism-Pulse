"""Tests for `visitor_pressure` - tourism_nights ÷ population, derived
(not independently fetched) once a place has both a tourism_nights
observation and a `place_demographics` row. See
ingestion.eurostat.service's module docstring and
pulse.visitor_pressure.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models import Destination, Place
from tourism_pulse_api.db.models.place_demographics import PlaceDemographics
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.parser import EurostatObservation
from tourism_pulse_api.ingestion.eurostat.service import (
    VISITOR_PRESSURE_SIGNAL_TYPE,
    build_visitor_pressure_preview,
    upsert_visitor_pressure_signal,
)
from tourism_pulse_api.pulse.visitor_pressure import (
    VISITOR_PRESSURE_REFERENCE_RATIO,
    normalize_visitor_pressure,
)


def make_nights_observation(value: float, *, year: int = 2025) -> EurostatObservation:
    return EurostatObservation(
        year=year,
        month=12,
        geo="AT",
        geo_name="Austria",
        value=Decimal(str(value)),
        unit="nights",
        period_start=date(year, 12, 1),
        period_end=date(year, 12, 31),
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
    destination = Destination(country_code="AT", name="Visitor Pressure Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Visitor Pressure Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


@pytest.fixture()
def demographics(db_session, test_place) -> PlaceDemographics:
    row = PlaceDemographics(
        place_id=test_place.id,
        year=2025,
        population=9_197_213,
        source="eurostat",
        retrieved_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# --- pulse.visitor_pressure normalizer ---------------------------------------


def test_normalize_zero_ratio_is_zero() -> None:
    assert normalize_visitor_pressure(0.0) == 0.0


def test_normalize_at_reference_ratio_is_full_marks() -> None:
    assert normalize_visitor_pressure(VISITOR_PRESSURE_REFERENCE_RATIO) == 1.0


def test_normalize_is_monotonic() -> None:
    assert normalize_visitor_pressure(0.1) < normalize_visitor_pressure(0.5)


# --- build_visitor_pressure_preview -------------------------------------------


def test_preview_computes_ratio(demographics) -> None:
    observation = make_nights_observation(8_616_613)

    preview = build_visitor_pressure_preview(
        tourism_nights_observation=observation, demographics=demographics
    )

    assert preview is not None
    assert preview.ratio == pytest.approx(8_616_613 / 9_197_213)
    assert preview.target_dimension == "capacity"


def test_preview_is_none_when_population_is_zero(db_session, test_place) -> None:
    zero_population = PlaceDemographics(
        place_id=test_place.id,
        year=2025,
        population=0,
        source="eurostat",
        retrieved_at=datetime.now(UTC),
    )

    preview = build_visitor_pressure_preview(
        tourism_nights_observation=make_nights_observation(1_000_000),
        demographics=zero_population,
    )

    assert preview is None


# --- upsert_visitor_pressure_signal -------------------------------------------


def test_upsert_creates_signal(db_session, test_place, demographics) -> None:
    observation = make_nights_observation(8_616_613)

    result = upsert_visitor_pressure_signal(
        db_session,
        place_id=test_place.id,
        tourism_nights_observation=observation,
        demographics=demographics,
        source_url="https://a",
    )

    assert result is not None
    signal, created, gate = result
    assert gate.accepted is True
    assert created is True
    assert signal.signal_type == VISITOR_PRESSURE_SIGNAL_TYPE
    assert signal.unit == "nights_per_resident"
    assert signal.source_observation_id == demographics.source_observation_id


def test_upsert_is_idempotent(db_session, test_place, demographics) -> None:
    observation = make_nights_observation(8_616_613)

    first_result = upsert_visitor_pressure_signal(
        db_session,
        place_id=test_place.id,
        tourism_nights_observation=observation,
        demographics=demographics,
        source_url="https://a",
    )
    second_result = upsert_visitor_pressure_signal(
        db_session,
        place_id=test_place.id,
        tourism_nights_observation=observation,
        demographics=demographics,
        source_url="https://b",
    )

    assert first_result is not None
    assert second_result is not None
    first_signal, first_created, _ = first_result
    second_signal, second_created, _ = second_result

    assert first_created is True
    assert second_created is False
    assert first_signal.id == second_signal.id


def test_upsert_returns_none_without_population(db_session, test_place) -> None:
    zero_population = PlaceDemographics(
        place_id=test_place.id,
        year=2025,
        population=0,
        source="eurostat",
        retrieved_at=datetime.now(UTC),
    )

    result = upsert_visitor_pressure_signal(
        db_session,
        place_id=test_place.id,
        tourism_nights_observation=make_nights_observation(1_000_000),
        demographics=zero_population,
        source_url="https://a",
    )

    assert result is None
