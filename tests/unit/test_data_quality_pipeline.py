"""Tests for run_quality_checks: DB-touching checks (duplicate, outlier)
and the accept/reject aggregation + DataQualityResult persistence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from tourism_pulse_api.data_quality.checks import check_duplicate, check_outlier
from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import SignalCandidate
from tourism_pulse_api.db.models import DataQualityResult, Destination, Place, Signal
from tourism_pulse_api.db.session import SessionLocal


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="DQ Pipeline Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="DQ Pipeline Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


def make_candidate(place_id: int, **overrides) -> SignalCandidate:
    defaults = dict(
        place_id=place_id,
        signal_type="weather_comfort",
        value=Decimal("50"),
        unit="score",
        observed_at=datetime.now(UTC),
        source="government",
    )
    return SignalCandidate(**{**defaults, **overrides})


# --- check_duplicate --------------------------------------------------


def test_duplicate_warns_on_conflicting_value(db_session, test_place) -> None:
    observed_at = datetime.now(UTC)
    db_session.add(
        Signal(
            place_id=test_place.id,
            signal_type="weather_comfort",
            value=Decimal("50"),
            unit="score",
            observed_at=observed_at,
            source="government",
        )
    )
    db_session.commit()

    candidate = make_candidate(
        test_place.id, observed_at=observed_at, value=Decimal("99")
    )

    outcome = check_duplicate(db_session, candidate)

    assert outcome.passed is False
    assert outcome.severity == "warn"


def test_duplicate_passes_identical_value(db_session, test_place) -> None:
    observed_at = datetime.now(UTC)
    db_session.add(
        Signal(
            place_id=test_place.id,
            signal_type="weather_comfort",
            value=Decimal("50"),
            unit="score",
            observed_at=observed_at,
            source="government",
        )
    )
    db_session.commit()

    candidate = make_candidate(
        test_place.id, observed_at=observed_at, value=Decimal("50")
    )

    outcome = check_duplicate(db_session, candidate)

    assert outcome.passed is True


def test_duplicate_passes_no_existing_row(db_session, test_place) -> None:
    outcome = check_duplicate(db_session, make_candidate(test_place.id))
    assert outcome.passed is True


# --- check_outlier --------------------------------------------------


def test_outlier_warns_on_extreme_value(db_session, test_place) -> None:
    now = datetime.now(UTC)
    for i, value in enumerate([50, 51, 49, 50, 52]):
        db_session.add(
            Signal(
                place_id=test_place.id,
                signal_type="weather_comfort",
                value=Decimal(str(value)),
                unit="score",
                observed_at=now - timedelta(days=i + 1),
                source="government",
            )
        )
    db_session.commit()

    candidate = make_candidate(test_place.id, value=Decimal("0"))
    outcome = check_outlier(db_session, candidate)

    assert outcome.passed is False
    assert outcome.severity == "warn"


def test_outlier_passes_consistent_value(db_session, test_place) -> None:
    now = datetime.now(UTC)
    for i, value in enumerate([50, 51, 49, 50, 52]):
        db_session.add(
            Signal(
                place_id=test_place.id,
                signal_type="weather_comfort",
                value=Decimal(str(value)),
                unit="score",
                observed_at=now - timedelta(days=i + 1),
                source="government",
            )
        )
    db_session.commit()

    candidate = make_candidate(test_place.id, value=Decimal("51"))
    outcome = check_outlier(db_session, candidate)

    assert outcome.passed is True


def test_outlier_passes_insufficient_history(db_session, test_place) -> None:
    outcome = check_outlier(db_session, make_candidate(test_place.id, value=Decimal("0")))
    assert outcome.passed is True


# --- run_quality_checks: aggregation + persistence -----------------------


def test_pipeline_accepts_clean_candidate(db_session, test_place) -> None:
    gate = run_quality_checks(db_session, make_candidate(test_place.id))

    assert gate.accepted is True
    assert len(gate.outcomes) == 7


def test_pipeline_rejects_on_reject_severity_failure(db_session, test_place) -> None:
    candidate = make_candidate(test_place.id, value=None)

    gate = run_quality_checks(db_session, candidate)

    assert gate.accepted is False


def test_pipeline_still_accepts_on_warn_only_failure(db_session, test_place) -> None:
    candidate = make_candidate(test_place.id, unit="   ")

    gate = run_quality_checks(db_session, candidate)

    assert gate.accepted is True
    assert any(not o.passed and o.severity == "warn" for o in gate.outcomes)


def test_pipeline_persists_one_result_row_per_check(db_session, test_place) -> None:
    before = db_session.query(DataQualityResult).count()

    run_quality_checks(db_session, make_candidate(test_place.id))

    after = db_session.query(DataQualityResult).count()

    assert after - before == 7


def test_pipeline_persisted_rows_reference_place_and_signal_type(db_session, test_place) -> None:
    run_quality_checks(db_session, make_candidate(test_place.id, signal_type="weather_comfort"))

    rows = (
        db_session.query(DataQualityResult)
        .filter(DataQualityResult.place_id == test_place.id)
        .all()
    )

    assert len(rows) == 7
    assert all(row.signal_type == "weather_comfort" for row in rows)
