"""Tests for EventCandidate's behavior through the data-quality checks -
the generalization that closes the gap noted in commit 8c786c9 (Event
had no value/unit/observed_at the way Signal does, so the original
SignalCandidate-shaped gate didn't apply to it)."""

from datetime import UTC, datetime, timedelta

from tourism_pulse_api.data_quality.checks import (
    check_duplicate,
    check_impossible_range,
    check_invalid_date,
    check_missing_value,
    check_outlier,
    check_stale,
)
from tourism_pulse_api.data_quality.types import EventCandidate, SignalCandidate
from tourism_pulse_api.db.session import SessionLocal


def make_event_candidate(**overrides) -> EventCandidate:
    defaults = dict(
        place_id=1,
        event_type="festival",
        start_at=datetime.now(UTC) + timedelta(days=30),
        source="ticketmaster",
    )
    return EventCandidate(**{**defaults, **overrides})


# --- numeric-only checks no-op cleanly for an Event candidate ----------------


def test_missing_value_does_not_reject_an_event_candidate() -> None:
    # The interesting/subtle part: EventCandidate.value is *always* None
    # (has_value=False), which must NOT be treated as a defect the way
    # it is for a SignalCandidate.
    outcome = check_missing_value(make_event_candidate())
    assert outcome.passed is True


def test_impossible_range_no_ops_for_an_event_candidate() -> None:
    outcome = check_impossible_range(make_event_candidate())
    assert outcome.passed is True


def test_duplicate_no_ops_for_an_event_candidate() -> None:
    session = SessionLocal()
    try:
        outcome = check_duplicate(session, make_event_candidate())
        assert outcome.passed is True
    finally:
        session.close()


def test_outlier_no_ops_for_an_event_candidate() -> None:
    session = SessionLocal()
    try:
        outcome = check_outlier(session, make_event_candidate())
        assert outcome.passed is True
    finally:
        session.close()


# --- date checks: the reason EventCandidate can't reuse SignalCandidate ------


def test_invalid_date_accepts_an_event_a_year_out() -> None:
    # A SignalCandidate with the same observed_at would be rejected (its
    # 1-hour future-skew tolerance) - EventCandidate's 3-year tolerance
    # must accept it.
    now = datetime.now(UTC)
    outcome = check_invalid_date(
        make_event_candidate(start_at=now + timedelta(days=365)), now=now
    )
    assert outcome.passed is True


def test_invalid_date_still_rejects_an_implausibly_old_event() -> None:
    outcome = check_invalid_date(make_event_candidate(start_at=datetime(1899, 1, 1, tzinfo=UTC)))
    assert outcome.passed is False
    assert outcome.severity == "reject"


def test_invalid_date_still_rejects_beyond_the_event_skew() -> None:
    now = datetime.now(UTC)
    outcome = check_invalid_date(
        make_event_candidate(start_at=now + timedelta(days=365 * 5)), now=now
    )
    assert outcome.passed is False


def test_signal_candidate_still_rejects_a_far_future_date_unchanged() -> None:
    # Confirms EventCandidate's wider tolerance is additive, not a
    # regression on SignalCandidate's existing (tighter) behavior.
    now = datetime.now(UTC)
    signal = SignalCandidate(
        place_id=1,
        signal_type="weather_comfort",
        value=None,
        unit=None,
        observed_at=now + timedelta(days=1),
        source="government",
    )
    outcome = check_invalid_date(signal, now=now)
    assert outcome.passed is False


def test_stale_does_not_flag_an_upcoming_event() -> None:
    # start_at is in the future, so "age" is negative - never stale.
    outcome = check_stale(make_event_candidate(start_at=datetime.now(UTC) + timedelta(days=60)))
    assert outcome.passed is True


def test_stale_warns_on_a_long_past_event() -> None:
    outcome = check_stale(
        make_event_candidate(start_at=datetime.now(UTC) - timedelta(days=90))
    )
    assert outcome.passed is False
    assert outcome.severity == "warn"
