import calendar
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.parser import EurostatObservation
from tourism_pulse_api.ingestion.eurostat.service import (
    build_preview,
    observed_at_for,
    select_observations,
    upsert_tourism_nights_signal,
)


def make_observation(
    year: int,
    month: int,
    value: int = 10_000_000,
    *,
    geo: str = "AT",
    geo_name: str = "Austria",
) -> EurostatObservation:
    last_day = calendar.monthrange(year, month)[1]

    return EurostatObservation(
        year=year,
        month=month,
        geo=geo,
        geo_name=geo_name,
        value=Decimal(value),
        unit="nights",
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
    destination = Destination(country_code="AT", name="Eurostat Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Eurostat Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_select_observations_defaults_to_latest() -> None:
    observations = [make_observation(2024, 6), make_observation(2025, 6)]

    result = select_observations(observations)

    assert len(result) == 1
    assert result[0].year == 2025


def test_select_observations_filters_by_month() -> None:
    observations = [make_observation(2024, 6), make_observation(2025, 6)]

    result = select_observations(observations, month="2024-06")

    assert len(result) == 1
    assert result[0].year == 2024


def test_select_observations_backfill_returns_all_sorted() -> None:
    observations = [make_observation(2025, 6), make_observation(2024, 6)]

    result = select_observations(observations, backfill=True)

    assert [o.year for o in result] == [2024, 2025]


def test_select_observations_invalid_month_format_raises() -> None:
    with pytest.raises(ValueError):
        select_observations([make_observation(2024, 6)], month="not-a-month")


def test_observed_at_uses_period_end_at_utc_midnight() -> None:
    observation = make_observation(2026, 5)

    assert observed_at_for(observation) == datetime(2026, 5, 31, 0, 0, tzinfo=UTC)


def test_build_preview_keeps_raw_and_normalized_values_separate() -> None:
    history = [make_observation(year, 6, 10_000_000) for year in range(2020, 2025)]
    target = make_observation(2025, 6, 15_000_000)

    preview = build_preview(target, [*history, target])

    assert preview.raw_value == 15_000_000.0
    assert preview.unit == "nights"
    assert preview.geo == "AT"
    assert preview.place_name == "Austria"
    assert preview.seasonal.status == "ok"
    assert 0.0 < preview.seasonal.score < 1.0
    assert preview.target_dimension == "demand"
    assert preview.seasonal.score != preview.raw_value


def test_upsert_creates_signal_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation(2026, 5, 8_616_613)

    signal, created, _ = upsert_tourism_nights_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tour_occ_nim?...",
    )

    assert created is True
    assert signal.place_id == test_place.id
    assert signal.signal_type == "tourism_nights"
    assert signal.value == Decimal(8_616_613)
    assert signal.unit == "nights"
    assert signal.source == "eurostat"
    assert signal.observed_at == datetime(2026, 5, 31, tzinfo=UTC)


def test_upsert_is_idempotent_on_repeated_ingestion(db_session, test_place) -> None:
    observation = make_observation(2026, 5, 8_616_613)

    first, first_created, _ = upsert_tourism_nights_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )
    second, second_created, _ = upsert_tourism_nights_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://b"
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
            Signal.source == "eurostat",
        )
        .count()
    )
    assert count == 1


def test_upsert_does_not_collide_with_a_ksh_signal_for_the_same_place(
    db_session, test_place
) -> None:
    # Same place, same observed_at, same signal_type - but a different
    # source. The uniqueness constraint is keyed on all four columns, so a
    # KSH-sourced and a Eurostat-sourced tourism_nights signal must coexist.
    ksh_signal = Signal(
        place_id=test_place.id,
        signal_type="tourism_nights",
        value=Decimal(1487),
        unit="thousand_nights",
        observed_at=datetime(2026, 5, 31, tzinfo=UTC),
        source="ksh",
    )
    db_session.add(ksh_signal)
    db_session.commit()

    observation = make_observation(2026, 5, 8_616_613)
    signal, created, _ = upsert_tourism_nights_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert created is True
    assert signal.id != ksh_signal.id


def test_upsert_records_source_observation_id(db_session, test_place) -> None:
    from tourism_pulse_api.db.models import Source
    from tourism_pulse_api.db.models.source_observation import SourceObservation

    # Seeded once for the whole test session (tests/conftest.py::_seed_sources).
    source = db_session.query(Source).filter(Source.name == "eurostat").one()

    observation_row = SourceObservation(
        source_id=source.id,
        dataset="eurostat_tour_occ_nim",
        retrieved_at=datetime.now(UTC),
        raw_payload="{}",
        content_type="application/json",
        checksum="x" * 64,
    )
    db_session.add(observation_row)
    db_session.commit()
    db_session.refresh(observation_row)

    observation = make_observation(2026, 6, 10_000_000)

    signal, _, gate = upsert_tourism_nights_signal(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://a",
        source_observation_id=observation_row.id,
    )

    assert signal.source_observation_id == observation_row.id
    assert gate.accepted is True


def test_upsert_rejects_impossible_negative_value(db_session, test_place) -> None:
    observation = make_observation(2026, 6, -5_000_000)

    signal, created, gate = upsert_tourism_nights_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert signal is None
    assert created is False
    assert gate.accepted is False
