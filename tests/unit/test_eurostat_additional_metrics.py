"""Tests for the arrivals and occupancy-rate Eurostat metrics.

Nights-spent already has its own dedicated test_eurostat_parser.py /
test_eurostat_ingestion.py - this file covers the two metrics added
alongside it (see ingestion.eurostat.parser / .service module docstrings).
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.parser import (
    ARRIVALS_UNIT,
    OCCUPANCY_UNIT,
    EurostatObservation,
    parse_eurostat_arrivals,
    parse_eurostat_occupancy_rate,
)
from tourism_pulse_api.ingestion.eurostat.service import (
    ARRIVALS_SIGNAL_TYPE,
    OCCUPANCY_RATE_SIGNAL_TYPE,
    build_arrivals_preview,
    build_occupancy_preview,
    upsert_arrivals_signal,
    upsert_occupancy_rate_signal,
)

ARRIVALS_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eurostat_tour_occ_arm_sample.json"
)
OCCUPANCY_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eurostat_tour_occ_mnor_sample.json"
)


# --- arrivals: parsing -------------------------------------------------------


def test_arrivals_parses_all_published_months() -> None:
    observations = parse_eurostat_arrivals(ARRIVALS_FIXTURE.read_text(encoding="utf-8"))

    assert len(observations) == 29


def test_arrivals_unit_is_arrivals_not_nights() -> None:
    observations = parse_eurostat_arrivals(ARRIVALS_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.unit == ARRIVALS_UNIT for o in observations)


def test_arrivals_geo_is_captured() -> None:
    observations = parse_eurostat_arrivals(ARRIVALS_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.geo == "AT" for o in observations)


def test_arrivals_invalid_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_eurostat_arrivals("not json")


# --- occupancy rate: parsing (different dimension shape: accomunit) --------


def test_occupancy_rate_parses_all_published_months() -> None:
    observations = parse_eurostat_occupancy_rate(OCCUPANCY_FIXTURE.read_text(encoding="utf-8"))

    assert len(observations) == 5


def test_occupancy_rate_unit_is_percent() -> None:
    observations = parse_eurostat_occupancy_rate(OCCUPANCY_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.unit == OCCUPANCY_UNIT for o in observations)


def test_occupancy_rate_values_match_the_fixture() -> None:
    observations = parse_eurostat_occupancy_rate(OCCUPANCY_FIXTURE.read_text(encoding="utf-8"))

    latest = next(o for o in observations if o.period == "2026-05")
    assert latest.value == Decimal("34.3")


def test_occupancy_rate_rejects_a_response_with_two_accomunit_categories() -> None:
    import json

    text = json.dumps(
        {
            "dimension": {
                "freq": {"category": {"index": {"M": 0}}},
                # Both BEDRM and BEDPL present - flat-index assumption breaks.
                "accomunit": {"category": {"index": {"BEDRM": 0, "BEDPL": 1}}},
                "unit": {"category": {"index": {"PC": 0}}},
                "geo": {"category": {"index": {"AT": 0}, "label": {"AT": "Austria"}}},
                "time": {"category": {"index": {"2026-01": 0}}},
            },
            "id": ["freq", "accomunit", "unit", "geo", "time"],
            "size": [1, 2, 1, 1, 1],
            "value": {"0": 67.2},
        }
    )

    with pytest.raises(ValueError):
        parse_eurostat_occupancy_rate(text)


# --- arrivals: ingestion (raw-only, no dimension) ---------------------------


def make_observation(
    year: int,
    month: int,
    value,
    *,
    unit: str,
    geo: str = "AT",
    geo_name: str = "Austria",
) -> EurostatObservation:
    import calendar

    last_day = calendar.monthrange(year, month)[1]

    return EurostatObservation(
        year=year,
        month=month,
        geo=geo,
        geo_name=geo_name,
        value=Decimal(str(value)),
        unit=unit,
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
    destination = Destination(country_code="AT", name="Eurostat Metrics Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Eurostat Metrics Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_arrivals_preview_reports_no_dimension() -> None:
    observation = make_observation(2026, 5, 3_378_684, unit=ARRIVALS_UNIT)

    preview = build_arrivals_preview(observation)

    assert preview.raw_value == 3_378_684.0
    assert "none" in preview.target_dimension.lower()


def test_arrivals_upsert_creates_signal(db_session, test_place) -> None:
    observation = make_observation(2026, 5, 3_378_684, unit=ARRIVALS_UNIT)

    signal, created, _ = upsert_arrivals_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert created is True
    assert signal.signal_type == ARRIVALS_SIGNAL_TYPE
    assert signal.value == Decimal(3_378_684)
    assert signal.unit == ARRIVALS_UNIT
    assert signal.source == "eurostat"


def test_arrivals_upsert_is_idempotent(db_session, test_place) -> None:
    observation = make_observation(2026, 5, 3_378_684, unit=ARRIVALS_UNIT)

    first, first_created, _ = upsert_arrivals_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )
    second, second_created, _ = upsert_arrivals_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://b"
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


def test_arrivals_and_nights_coexist_for_the_same_place_and_period(db_session, test_place) -> None:
    # Same place, same observed_at - but a different signal_type, so the
    # uniqueness constraint (place_id, signal_type, observed_at, source)
    # must not treat these as the same row.
    nights_signal = Signal(
        place_id=test_place.id,
        signal_type="tourism_nights",
        value=Decimal(8_616_613),
        unit="nights",
        observed_at=datetime(2026, 5, 31, tzinfo=UTC),
        source="eurostat",
    )
    db_session.add(nights_signal)
    db_session.commit()

    arrivals_observation = make_observation(2026, 5, 3_378_684, unit=ARRIVALS_UNIT)
    arrivals_signal, created, _ = upsert_arrivals_signal(
        db_session, place_id=test_place.id, observation=arrivals_observation, source_url="https://a"
    )

    assert created is True
    assert arrivals_signal.id != nights_signal.id


# --- occupancy rate: ingestion (direct percentage, feeds demand) -----------


def test_occupancy_preview_normalizes_percentage_directly() -> None:
    observation = make_observation(2026, 5, 34.3, unit=OCCUPANCY_UNIT)

    preview = build_occupancy_preview(observation)

    assert preview.raw_value == 34.3
    assert preview.normalized_value == pytest.approx(0.343)
    assert preview.target_dimension == "demand"


def test_occupancy_preview_clamps_out_of_range_values() -> None:
    over = make_observation(2026, 5, 150.0, unit=OCCUPANCY_UNIT)
    under = make_observation(2026, 5, -10.0, unit=OCCUPANCY_UNIT)

    assert build_occupancy_preview(over).normalized_value == 1.0
    assert build_occupancy_preview(under).normalized_value == 0.0


def test_occupancy_upsert_creates_signal(db_session, test_place) -> None:
    observation = make_observation(2026, 5, 34.3, unit=OCCUPANCY_UNIT)

    signal, created, _ = upsert_occupancy_rate_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert created is True
    assert signal.signal_type == OCCUPANCY_RATE_SIGNAL_TYPE
    assert signal.value == Decimal("34.3")
    assert signal.unit == OCCUPANCY_UNIT


def test_occupancy_upsert_is_idempotent(db_session, test_place) -> None:
    observation = make_observation(2026, 5, 34.3, unit=OCCUPANCY_UNIT)

    first, first_created, _ = upsert_occupancy_rate_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )
    second, second_created, _ = upsert_occupancy_rate_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://b"
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
