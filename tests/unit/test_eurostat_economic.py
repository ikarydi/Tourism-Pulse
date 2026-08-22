"""Tests for the Eurostat `sts_setu_a` (accommodation-sector turnover
growth) metric - the first signal to feed the `economic` dimension.

Annual, same shape as capacity/population, so parsing reuses
`_parse_annual_country_series` unchanged. The fixture is real (trimmed)
Eurostat data for Austria, including the COVID-era swings (-34.7% in
2020, +75.5% in the 2022 rebound) that exercise
pulse.economic_growth's clamping.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from tourism_pulse_api.db.models import Destination, Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.parser import (
    ECONOMIC_UNIT,
    EurostatObservation,
    parse_eurostat_turnover_growth,
)
from tourism_pulse_api.ingestion.eurostat.service import (
    TOURISM_TURNOVER_GROWTH_SIGNAL_TYPE,
    build_economic_preview,
    upsert_economic_signal,
)
from tourism_pulse_api.pulse.economic_growth import (
    GROWTH_RATE_CLAMP_PERCENT,
    normalize_turnover_growth,
)

ECONOMIC_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eurostat_sts_setu_a_sample.json"
)


# --- parsing -----------------------------------------------------------------


def test_economic_parses_all_published_years() -> None:
    observations = parse_eurostat_turnover_growth(ECONOMIC_FIXTURE.read_text(encoding="utf-8"))

    assert [o.year for o in observations] == [2020, 2021, 2022, 2023, 2024, 2025]


def test_economic_unit() -> None:
    observations = parse_eurostat_turnover_growth(ECONOMIC_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.unit == ECONOMIC_UNIT for o in observations)


def test_economic_values_can_be_negative() -> None:
    # 2020's COVID-crash figure, straight from the fixture.
    observations = parse_eurostat_turnover_growth(ECONOMIC_FIXTURE.read_text(encoding="utf-8"))

    year_2020 = next(o for o in observations if o.year == 2020)
    assert year_2020.value == Decimal("-34.7")


def test_economic_invalid_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_eurostat_turnover_growth("not json")


# --- pulse.economic_growth normalizer -----------------------------------------


def test_normalize_zero_growth_is_midpoint() -> None:
    assert normalize_turnover_growth(0.0) == pytest.approx(0.5)


def test_normalize_positive_growth_scores_above_midpoint() -> None:
    assert normalize_turnover_growth(10.0) > 0.5


def test_normalize_negative_growth_scores_below_midpoint() -> None:
    assert normalize_turnover_growth(-10.0) < 0.5


def test_normalize_clamps_extreme_positive_growth() -> None:
    # 2022's real +75.5% rebound - far past the clamp, must saturate at 1.0.
    assert normalize_turnover_growth(75.5) == 1.0
    assert normalize_turnover_growth(GROWTH_RATE_CLAMP_PERCENT) == 1.0


def test_normalize_clamps_extreme_negative_growth() -> None:
    # 2020's real -34.7% crash - far past the clamp, must floor at 0.0.
    assert normalize_turnover_growth(-34.7) == 0.0
    assert normalize_turnover_growth(-GROWTH_RATE_CLAMP_PERCENT) == 0.0


# --- ingestion: feeds economic ------------------------------------------------


def make_annual_observation(
    year: int, value, *, unit: str = ECONOMIC_UNIT, geo: str = "AT", geo_name: str = "Austria"
) -> EurostatObservation:
    return EurostatObservation(
        year=year,
        month=12,
        geo=geo,
        geo_name=geo_name,
        value=Decimal(str(value)),
        unit=unit,
        period_start=date(year, 1, 1),
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
    destination = Destination(country_code="AT", name="Eurostat Economic Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Eurostat Economic Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_economic_preview_targets_economic_dimension() -> None:
    preview = build_economic_preview(make_annual_observation(2025, 4.3))

    assert preview.target_dimension == "economic"
    assert preview.raw_value == 4.3
    assert 0.0 <= preview.normalized_value <= 1.0


def test_economic_upsert_creates_signal(db_session, test_place) -> None:
    observation = make_annual_observation(2025, 4.3)

    signal, created, gate = upsert_economic_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert gate.accepted is True
    assert created is True
    assert signal.signal_type == TOURISM_TURNOVER_GROWTH_SIGNAL_TYPE
    assert signal.value == Decimal("4.3")
    assert signal.unit == ECONOMIC_UNIT
    assert signal.source == "eurostat"


def test_economic_upsert_is_idempotent(db_session, test_place) -> None:
    observation = make_annual_observation(2025, 4.3)

    first, first_created, _ = upsert_economic_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )
    second, second_created, _ = upsert_economic_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://b"
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


def test_economic_upsert_accepts_negative_value(db_session, test_place) -> None:
    # 2020's COVID-crash figure must pass the quality gate - a shrinking
    # sector is a real, valid observation, not a defect.
    observation = make_annual_observation(2020, -34.7)

    signal, created, gate = upsert_economic_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert gate.accepted is True
    assert signal.value == Decimal("-34.7")
