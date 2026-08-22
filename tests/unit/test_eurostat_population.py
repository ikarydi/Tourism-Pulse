"""Tests for the Eurostat `demo_pjan` (population) metric.

Reference data, not a Signal - see db/models/place_demographics.py and
ingestion.eurostat.service's module docstring. Annual, same shape as
capacity (test_eurostat_capacity.py), so parsing reuses
`_parse_annual_country_series` unchanged - these tests focus on the
thin wrapper and the place_demographics upsert, not re-testing the
shared annual-series engine.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from tourism_pulse_api.db.models import Destination, Place, Source
from tourism_pulse_api.db.models.place_demographics import PlaceDemographics
from tourism_pulse_api.db.models.source_observation import SourceObservation
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.parser import (
    POPULATION_UNIT,
    parse_eurostat_population,
)
from tourism_pulse_api.ingestion.eurostat.service import upsert_population

POPULATION_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eurostat_demo_pjan_sample.json"
)


# --- parsing -----------------------------------------------------------------


def test_population_parses_all_published_years() -> None:
    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))

    assert [o.year for o in observations] == [2020, 2021, 2022, 2023, 2024, 2025]


def test_population_unit() -> None:
    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.unit == POPULATION_UNIT for o in observations)


def test_population_values_match_the_fixture() -> None:
    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))

    latest = next(o for o in observations if o.year == 2025)
    assert latest.value == 9_197_213


def test_population_geo_is_captured() -> None:
    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.geo == "AT" for o in observations)
    assert observations[0].geo_name == "Austria"


def test_population_invalid_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_eurostat_population("not json")


# --- ingestion: reference data, not a Signal ---------------------------------


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="AT", name="Eurostat Population Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Eurostat Population Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_upsert_population_creates_row(db_session, test_place) -> None:
    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))
    observation = next(o for o in observations if o.year == 2025)

    row = upsert_population(db_session, place_id=test_place.id, observation=observation)

    assert isinstance(row, PlaceDemographics)
    assert row.place_id == test_place.id
    assert row.year == 2025
    assert row.population == 9_197_213
    assert row.source == "eurostat"


def test_upsert_population_is_idempotent_per_year(db_session, test_place) -> None:
    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))
    observation = next(o for o in observations if o.year == 2025)

    first = upsert_population(db_session, place_id=test_place.id, observation=observation)
    second = upsert_population(db_session, place_id=test_place.id, observation=observation)

    assert first.id == second.id
    assert (
        db_session.query(PlaceDemographics)
        .filter(PlaceDemographics.place_id == test_place.id)
        .count()
        == 1
    )


def test_upsert_population_sets_retrieved_at(db_session, test_place) -> None:
    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))
    observation = next(o for o in observations if o.year == 2025)

    row = upsert_population(db_session, place_id=test_place.id, observation=observation)

    assert row.retrieved_at.tzinfo is not None
    assert row.retrieved_at <= datetime.now(UTC)


def test_upsert_population_records_source_observation_id(db_session, test_place) -> None:
    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "eurostat").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="eurostat_demo_pjan",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    observations = parse_eurostat_population(POPULATION_FIXTURE.read_text(encoding="utf-8"))
    observation = next(o for o in observations if o.year == 2025)

    row = upsert_population(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_observation_id=observation_row.id,
    )

    assert row.source_observation_id == observation_row.id
