import calendar
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.ksh_capacity.parser import KshCapacityObservation
from tourism_pulse_api.ingestion.ksh_capacity.service import (
    build_preview,
    observed_at_for,
    select_observations,
    upsert_capacity_signal,
)


def make_observation(
    year: int,
    month: int,
    value: int = 300000,
    *,
    metric: str = "bed_places",
    unit: str = "beds",
) -> KshCapacityObservation:
    last_day = calendar.monthrange(year, month)[1]

    return KshCapacityObservation(
        year=year,
        month=month,
        metric=metric,
        value=Decimal(value),
        unit=unit,
        place_name="Hungary",
        period_start=date(year, month, 1),
        period_end=date(year, month, last_day),
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
    destination = Destination(country_code="HU", name="KSH Capacity Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="KSH Capacity Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_select_observations_defaults_to_latest() -> None:
    observations = [make_observation(2021, 6), make_observation(2022, 6)]

    result = select_observations(observations)

    assert len(result) == 1
    assert result[0].year == 2022


def test_select_observations_filters_by_month() -> None:
    observations = [make_observation(2021, 6), make_observation(2022, 6)]

    result = select_observations(observations, month="2021-06")

    assert len(result) == 1
    assert result[0].year == 2021


def test_select_observations_backfill_returns_all_sorted() -> None:
    observations = [make_observation(2022, 6), make_observation(2021, 6)]

    result = select_observations(observations, backfill=True)

    assert [o.year for o in result] == [2021, 2022]


def test_select_observations_invalid_month_format_raises() -> None:
    with pytest.raises(ValueError):
        select_observations([make_observation(2021, 6)], month="not-a-month")


def test_observed_at_uses_period_end_at_utc_midnight() -> None:
    observation = make_observation(2026, 6)

    assert observed_at_for(observation) == datetime(2026, 6, 30, 0, 0, tzinfo=UTC)


def test_build_preview_keeps_raw_and_normalized_values_separate() -> None:
    history = [make_observation(year, 6, 300000) for year in range(2020, 2025)]
    target = make_observation(2025, 6, 450000)

    preview = build_preview(target, [*history, target])

    assert preview.raw_value == 450000.0
    assert preview.unit == "beds"
    assert preview.metric == "bed_places"
    assert preview.seasonal.status == "ok"
    assert 0.0 < preview.seasonal.score < 1.0
    assert preview.target_dimension == "capacity"
    assert preview.seasonal.score != preview.raw_value


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(2026, 6, 525300)

    signal, created, _ = upsert_capacity_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://www.ksh.hu/stadat_files/tur/en/tur0071.csv",
    )

    assert created is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "accommodation_capacity"
    assert signal.value == Decimal(525300)
    assert signal.unit == "beds"
    assert signal.source == "ksh"
    assert signal.source_url == "https://www.ksh.hu/stadat_files/tur/en/tur0071.csv"
    assert signal.observed_at == datetime(2026, 6, 30, tzinfo=UTC)


def test_upsert_is_idempotent_on_repeated_ingestion(db_session, test_place) -> None:
    observation = make_observation(2026, 6, 525300)

    first, first_created, _ = upsert_capacity_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://example.com/a.csv",
    )
    second, second_created, _ = upsert_capacity_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://example.com/b.csv",
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id

    count = (
        db_session.query(Signal)
        .filter(
            Signal.place_id == test_place.id,
            Signal.signal_type == "accommodation_capacity",
            Signal.observed_at == observed_at_for(observation),
            Signal.source == "ksh",
        )
        .count()
    )

    assert count == 1


def test_upsert_refreshes_value_on_a_data_revision(db_session, test_place) -> None:
    observation = make_observation(2026, 6, 300000)

    original, _, _ = upsert_capacity_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://example.com/a.csv",
    )
    assert original.value == Decimal(300000)

    revised_observation = make_observation(2026, 6, 310000)

    revised, created_again, _ = upsert_capacity_signal(
        db_session,
        place_id=test_place.id,
        observation=revised_observation,
        source_url="https://example.com/a.csv",
    )

    assert created_again is False
    assert revised.id == original.id
    assert revised.value == Decimal(310000)


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    from tourism_pulse_api.db.models import Source
    from tourism_pulse_api.db.models.source_observation import SourceObservation

    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "ksh").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="ksh_stadat_27_2_1_13",
        retrieved_at=datetime.now(UTC),
        raw_payload="year,month,metric,value\n",
        content_type="text/csv",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    observation = make_observation(2026, 6, 525300)

    signal, _, gate = upsert_capacity_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://example.com/a.csv",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True


def test_upsert_rejects_impossible_negative_value(db_session, test_place) -> None:
    observation = make_observation(2026, 6, -1000)

    signal, created, gate = upsert_capacity_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://example.com/a.csv",
    )

    assert signal is None
    assert created is False
    assert gate.accepted is False
