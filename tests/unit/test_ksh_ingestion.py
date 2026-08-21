import calendar
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.ksh.parser import KshObservation
from tourism_pulse_api.ingestion.ksh.service import (
    build_preview,
    observed_at_for,
    select_observations,
    upsert_tourism_nights_signal,
)


def make_observation(
    year: int,
    month: int,
    domestic: int = 100,
    international: int = 200,
    *,
    region: str = "budapest",
    place_name: str = "Budapest",
) -> KshObservation:
    last_day = calendar.monthrange(year, month)[1]

    return KshObservation(
        year=year,
        month=month,
        region=region,
        domestic_nights=Decimal(domestic),
        international_nights=Decimal(international),
        total_nights=Decimal(domestic + international),
        unit="thousand_nights",
        place_name=place_name,
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
    destination = Destination(country_code="HU", name="KSH Ingestion Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="KSH Ingestion Test Place",
        place_type="destination",
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


def test_select_observations_empty_input() -> None:
    assert select_observations([]) == []


def test_observed_at_uses_period_end_at_utc_midnight() -> None:
    observation = make_observation(2026, 6)

    assert observed_at_for(observation) == datetime(2026, 6, 30, 0, 0, tzinfo=UTC)


def test_build_preview_keeps_raw_and_normalized_values_separate() -> None:
    history = [make_observation(year, 6, 100, 100) for year in range(2020, 2025)]
    target = make_observation(2025, 6, 150, 150)

    preview = build_preview(target, [*history, target])

    assert preview.raw_value == 300.0
    assert preview.unit == "thousand_nights"
    assert preview.seasonal.status == "ok"
    assert 0.0 < preview.seasonal.score < 1.0
    assert preview.target_dimension == "demand"
    # the normalized score must never be the same number as the raw value
    assert preview.seasonal.score != preview.raw_value


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(2026, 6, 196, 1291)

    signal, created = upsert_tourism_nights_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://www.ksh.hu/stadat_files/tur/en/tur0081.csv",
    )

    assert created is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "tourism_nights"
    assert signal.value == Decimal(1487)
    assert signal.unit == "thousand_nights"
    assert signal.source == "ksh"
    assert signal.source_url == "https://www.ksh.hu/stadat_files/tur/en/tur0081.csv"
    assert signal.observed_at == datetime(2026, 6, 30, tzinfo=UTC)


def test_upsert_is_idempotent_on_repeated_ingestion(db_session, test_place) -> None:
    observation = make_observation(2026, 6, 196, 1291)

    first, first_created = upsert_tourism_nights_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://example.com/a.csv",
    )
    second, second_created = upsert_tourism_nights_signal(
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
            Signal.signal_type == "tourism_nights",
            Signal.observed_at == observed_at_for(observation),
            Signal.source == "ksh",
        )
        .count()
    )

    assert count == 1


def test_upsert_refreshes_value_on_a_data_revision(db_session, test_place) -> None:
    observation = make_observation(2026, 6, 100, 100)

    original, _ = upsert_tourism_nights_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://example.com/a.csv",
    )
    assert original.value == Decimal(200)

    revised_observation = make_observation(2026, 6, 110, 110)

    revised, created_again = upsert_tourism_nights_signal(
        db_session,
        place_id=test_place.id,
        observation=revised_observation,
        source_url="https://example.com/a.csv",
    )

    assert created_again is False
    assert revised.id == original.id
    assert revised.value == Decimal(220)


def test_upsert_does_not_collide_across_different_places(db_session) -> None:
    destination = Destination(country_code="HU", name="KSH Ingestion Test Destination B")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place_a = Place(destination_id=destination.id, name="Place A", place_type="destination")
    place_b = Place(destination_id=destination.id, name="Place B", place_type="destination")
    db_session.add_all([place_a, place_b])
    db_session.commit()
    db_session.refresh(place_a)
    db_session.refresh(place_b)

    observation = make_observation(2026, 6, 196, 1291)

    signal_a, created_a = upsert_tourism_nights_signal(
        db_session,
        place_id=place_a.id,
        observation=observation,
        source_url="https://example.com/a.csv",
    )
    signal_b, created_b = upsert_tourism_nights_signal(
        db_session,
        place_id=place_b.id,
        observation=observation,
        source_url="https://example.com/a.csv",
    )

    assert created_a is True
    assert created_b is True
    assert signal_a.id != signal_b.id
