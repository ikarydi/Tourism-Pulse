"""Tests for the Eurostat `tour_cap_nat` (capacity) metric.

Distinct from the other three Eurostat metrics (test_eurostat_additional_metrics.py)
because it is annual, not monthly: its `time` dimension is a bare year, and
each observation is stamped as December of that year so it flows through
`pulse.seasonal_signal_adapter`'s "same calendar month" baseline unchanged
(see ingestion.eurostat.parser._parse_annual_country_series).
"""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.parser import (
    CAPACITY_UNIT,
    EurostatObservation,
    parse_eurostat_capacity,
)
from tourism_pulse_api.ingestion.eurostat.service import (
    ACCOMMODATION_CAPACITY_SIGNAL_TYPE,
    build_capacity_preview,
    upsert_capacity_signal,
)

CAPACITY_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eurostat_tour_cap_nat_sample.json"
)


# --- parsing -----------------------------------------------------------------


def test_capacity_parses_all_published_years() -> None:
    observations = parse_eurostat_capacity(CAPACITY_FIXTURE.read_text(encoding="utf-8"))

    # Fixture spans 1990-2026 (37 years); 2026 has no published value yet.
    assert len(observations) == 36


def test_capacity_unit_is_bed_places() -> None:
    observations = parse_eurostat_capacity(CAPACITY_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.unit == CAPACITY_UNIT for o in observations)


def test_capacity_every_observation_is_stamped_december() -> None:
    observations = parse_eurostat_capacity(CAPACITY_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.month == 12 for o in observations)
    assert all(o.period_end == date(o.year, 12, 31) for o in observations)


def test_capacity_geo_is_captured() -> None:
    observations = parse_eurostat_capacity(CAPACITY_FIXTURE.read_text(encoding="utf-8"))

    assert all(o.geo == "AT" for o in observations)


def test_capacity_values_match_the_fixture() -> None:
    observations = parse_eurostat_capacity(CAPACITY_FIXTURE.read_text(encoding="utf-8"))

    latest = next(o for o in observations if o.year == 2025)
    assert latest.value == Decimal("1167138")


def test_capacity_period_string_is_year_dash_twelve() -> None:
    observations = parse_eurostat_capacity(CAPACITY_FIXTURE.read_text(encoding="utf-8"))

    latest = next(o for o in observations if o.year == 2025)
    assert latest.period == "2025-12"


def test_capacity_invalid_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_eurostat_capacity("not json")


def test_capacity_rejects_a_response_with_two_accomunit_categories() -> None:
    text = json.dumps(
        {
            "dimension": {
                "freq": {"category": {"index": {"A": 0}}},
                "accomunit": {"category": {"index": {"BEDRM": 0, "BEDPL": 1}}},
                "unit": {"category": {"index": {"NR": 0}}},
                "nace_r2": {"category": {"index": {"I551-I553": 0}}},
                "geo": {"category": {"index": {"AT": 0}, "label": {"AT": "Austria"}}},
                "time": {"category": {"index": {"2024": 0}}},
            },
            "id": ["freq", "accomunit", "unit", "nace_r2", "geo", "time"],
            "size": [1, 2, 1, 1, 1, 1],
            "value": {"0": 1167138},
        }
    )

    with pytest.raises(ValueError):
        parse_eurostat_capacity(text)


def test_capacity_skips_years_with_no_published_value() -> None:
    text = json.dumps(
        {
            "dimension": {
                "freq": {"category": {"index": {"A": 0}}},
                "accomunit": {"category": {"index": {"BEDPL": 0}}},
                "unit": {"category": {"index": {"NR": 0}}},
                "nace_r2": {"category": {"index": {"I551-I553": 0}}},
                "geo": {"category": {"index": {"AT": 0}, "label": {"AT": "Austria"}}},
                "time": {"category": {"index": {"2024": 0, "2025": 1}}},
            },
            "id": ["freq", "accomunit", "unit", "nace_r2", "geo", "time"],
            "size": [1, 1, 1, 1, 1, 2],
            # 2025 (flat index 1) has no entry - not yet published.
            "value": {"0": 1064863},
        }
    )

    observations = parse_eurostat_capacity(text)

    assert [o.year for o in observations] == [2024]


# --- ingestion: seasonal normalization, feeds capacity ----------------------


def make_annual_observation(
    year: int, value, *, unit: str = CAPACITY_UNIT, geo: str = "AT", geo_name: str = "Austria"
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
    destination = Destination(country_code="AT", name="Eurostat Capacity Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Eurostat Capacity Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_capacity_preview_targets_capacity_dimension() -> None:
    series = [make_annual_observation(year, 1_000_000 + year) for year in range(2020, 2026)]
    latest = series[-1]

    preview = build_capacity_preview(latest, series)

    assert preview.target_dimension == "capacity"


def test_capacity_preview_reports_insufficient_baseline_with_too_little_history() -> None:
    series = [make_annual_observation(2026, 1_000_000)]

    preview = build_capacity_preview(series[0], series)

    assert preview.seasonal.status == "insufficient_baseline"


def test_capacity_preview_scores_against_prior_years() -> None:
    series = [make_annual_observation(year, 1_000_000) for year in range(2020, 2025)] + [
        make_annual_observation(2025, 1_200_000)
    ]
    latest = series[-1]

    preview = build_capacity_preview(latest, series)

    assert preview.seasonal.status == "ok"
    assert preview.seasonal.ratio == pytest.approx(1.2)
    assert preview.seasonal.score is not None
    assert preview.seasonal.score > 0.5  # above baseline -> above the midpoint


def test_capacity_upsert_creates_signal(db_session, test_place) -> None:
    observation = make_annual_observation(2025, 1_167_138)

    signal, created, _ = upsert_capacity_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )

    assert created is True
    assert signal.signal_type == ACCOMMODATION_CAPACITY_SIGNAL_TYPE
    assert signal.value == Decimal(1_167_138)
    assert signal.unit == CAPACITY_UNIT
    assert signal.source == "eurostat"


def test_capacity_upsert_is_idempotent(db_session, test_place) -> None:
    observation = make_annual_observation(2025, 1_167_138)

    first, first_created, _ = upsert_capacity_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )
    second, second_created, _ = upsert_capacity_signal(
        db_session, place_id=test_place.id, observation=observation, source_url="https://b"
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


def test_capacity_and_nights_coexist_for_the_same_place(db_session, test_place) -> None:
    nights_signal = Signal(
        place_id=test_place.id,
        signal_type="tourism_nights",
        value=Decimal(8_616_613),
        unit="nights",
        observed_at=datetime(2025, 12, 31, tzinfo=UTC),
        source="eurostat",
    )
    db_session.add(nights_signal)
    db_session.commit()

    capacity_observation = make_annual_observation(2025, 1_167_138)
    capacity_signal, created, _ = upsert_capacity_signal(
        db_session, place_id=test_place.id, observation=capacity_observation, source_url="https://a"
    )

    assert created is True
    assert capacity_signal.id != nights_signal.id
