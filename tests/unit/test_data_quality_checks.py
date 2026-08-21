"""Tests for individual data-quality checks (spec section 14)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tourism_pulse_api.data_quality.checks import (
    check_impossible_range,
    check_invalid_date,
    check_invalid_unit,
    check_missing_value,
    check_schema_change,
    check_source_failure,
    check_stale,
)
from tourism_pulse_api.data_quality.types import SignalCandidate
from tourism_pulse_api.db.models import Source
from tourism_pulse_api.db.session import SessionLocal


def make_candidate(**overrides) -> SignalCandidate:
    defaults = dict(
        place_id=1,
        signal_type="weather_comfort",
        value=Decimal("50"),
        unit="score",
        observed_at=datetime.now(UTC),
        source="government",
    )
    return SignalCandidate(**{**defaults, **overrides})


# --- check_missing_value --------------------------------------------------


def test_missing_value_rejects_none() -> None:
    outcome = check_missing_value(make_candidate(value=None))
    assert outcome.passed is False
    assert outcome.severity == "reject"


def test_missing_value_passes_present_value() -> None:
    outcome = check_missing_value(make_candidate())
    assert outcome.passed is True


# --- check_invalid_unit ---------------------------------------------------


def test_invalid_unit_rejects_blank_string() -> None:
    outcome = check_invalid_unit(make_candidate(unit="   "))
    assert outcome.passed is False
    assert outcome.severity == "warn"


def test_invalid_unit_passes_none() -> None:
    # unit is legitimately optional - None is not a defect.
    outcome = check_invalid_unit(make_candidate(unit=None))
    assert outcome.passed is True


def test_invalid_unit_passes_real_unit() -> None:
    outcome = check_invalid_unit(make_candidate(unit="celsius"))
    assert outcome.passed is True


# --- check_invalid_date ----------------------------------------------------


def test_invalid_date_rejects_missing() -> None:
    outcome = check_invalid_date(make_candidate(observed_at=None))
    assert outcome.passed is False
    assert outcome.severity == "reject"


def test_invalid_date_rejects_far_future() -> None:
    now = datetime.now(UTC)
    outcome = check_invalid_date(
        make_candidate(observed_at=now + timedelta(days=1)), now=now
    )
    assert outcome.passed is False


def test_invalid_date_rejects_implausibly_old() -> None:
    now = datetime.now(UTC)
    outcome = check_invalid_date(
        make_candidate(observed_at=datetime(1800, 1, 1, tzinfo=UTC)), now=now
    )
    assert outcome.passed is False


def test_invalid_date_passes_recent() -> None:
    now = datetime.now(UTC)
    outcome = check_invalid_date(
        make_candidate(observed_at=now - timedelta(hours=1)), now=now
    )
    assert outcome.passed is True


# --- check_impossible_range ------------------------------------------------


def test_impossible_range_rejects_out_of_bounds() -> None:
    outcome = check_impossible_range(
        make_candidate(signal_type="weather_comfort", value=Decimal("150"))
    )
    assert outcome.passed is False
    assert outcome.severity == "reject"


def test_impossible_range_rejects_negative_count() -> None:
    outcome = check_impossible_range(
        make_candidate(signal_type="tourism_nights", value=Decimal("-5"))
    )
    assert outcome.passed is False


def test_impossible_range_passes_within_bounds() -> None:
    outcome = check_impossible_range(
        make_candidate(signal_type="weather_comfort", value=Decimal("75"))
    )
    assert outcome.passed is True


def test_impossible_range_passes_unbounded_signal_type() -> None:
    outcome = check_impossible_range(
        make_candidate(signal_type="some_future_signal_type", value=Decimal("-999"))
    )
    assert outcome.passed is True


def test_impossible_range_skips_missing_value() -> None:
    # check_missing_value is the authoritative record of this defect.
    outcome = check_impossible_range(make_candidate(value=None))
    assert outcome.passed is True


# --- check_stale -------------------------------------------------------


def test_stale_warns_past_threshold() -> None:
    now = datetime.now(UTC)
    outcome = check_stale(
        make_candidate(
            signal_type="weather_comfort",
            observed_at=now - timedelta(days=10),
        ),
        now=now,
    )
    assert outcome.passed is False
    assert outcome.severity == "warn"


def test_stale_passes_within_threshold() -> None:
    now = datetime.now(UTC)
    outcome = check_stale(
        make_candidate(
            signal_type="accommodation_capacity_annual",
            observed_at=now - timedelta(days=10),
        ),
        now=now,
    )
    assert outcome.passed is True


def test_stale_skips_missing_date() -> None:
    outcome = check_stale(make_candidate(observed_at=None))
    assert outcome.passed is True


# --- archive-boundary checks ---------------------------------------------


def test_source_failure_rejects_empty_payload() -> None:
    outcome = check_source_failure("   ")
    assert outcome.passed is False
    assert outcome.severity == "reject"


def test_source_failure_passes_nonempty_payload() -> None:
    outcome = check_source_failure('{"ok": true}')
    assert outcome.passed is True


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def test_source(request, db_session) -> Source:
    source = Source(
        name=f"test_schema_source_{request.node.name}",
        category="commercial",
        reliability="0.900",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


def test_schema_change_passes_when_no_prior_version(db_session, test_source) -> None:
    outcome = check_schema_change(
        db_session,
        source_id=test_source.id,
        dataset="test_dataset",
        schema_version="v1",
    )
    assert outcome.passed is True


def test_schema_change_passes_when_none_given() -> None:
    session = SessionLocal()
    try:
        outcome = check_schema_change(
            session, source_id=1, dataset="test_dataset", schema_version=None
        )
    finally:
        session.close()

    assert outcome.passed is True


def test_schema_change_warns_on_version_change(db_session, test_source) -> None:
    from tourism_pulse_api.db.models.source_observation import SourceObservation

    db_session.add(
        SourceObservation(
            source_id=test_source.id,
            dataset="test_dataset",
            retrieved_at=datetime.now(UTC) - timedelta(days=1),
            raw_payload="{}",
            content_type="application/json",
            checksum="x" * 64,
            schema_version="v1",
        )
    )
    db_session.commit()

    outcome = check_schema_change(
        db_session,
        source_id=test_source.id,
        dataset="test_dataset",
        schema_version="v2",
    )

    assert outcome.passed is False
    assert outcome.severity == "warn"
