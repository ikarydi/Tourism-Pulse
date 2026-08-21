"""Runs the full per-candidate quality gate and persists its outcomes."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.checks import (
    check_duplicate,
    check_impossible_range,
    check_invalid_date,
    check_invalid_unit,
    check_missing_value,
    check_outlier,
    check_stale,
)
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.data_quality_result import DataQualityResult


def run_quality_checks(
    db: Session,
    candidate: SignalCandidate,
    *,
    now: datetime | None = None,
) -> QualityGateResult:
    """Runs every per-candidate check, persists one DataQualityResult row
    per outcome (pass and fail alike, per spec section 13's "how reliable
    is it" traceability), and reports whether the candidate is accepted.

    A candidate is accepted unless at least one check fails at
    severity="reject" - "warn" failures are recorded but never block the
    write. Callers (adapter service.py upsert functions) should skip the
    Signal write when `accepted` is False; the already-archived
    SourceObservation row is left untouched either way (spec 12.1).
    """

    checked_at = now or datetime.now(UTC)

    outcomes = [
        check_missing_value(candidate),
        check_invalid_unit(candidate),
        check_invalid_date(candidate, now=checked_at),
        check_impossible_range(candidate),
        check_duplicate(db, candidate),
        check_outlier(db, candidate),
        check_stale(candidate, now=checked_at),
    ]

    for outcome in outcomes:
        db.add(
            DataQualityResult(
                source_observation_id=candidate.source_observation_id,
                place_id=candidate.place_id,
                signal_type=candidate.signal_type,
                check_name=outcome.check_name,
                passed=outcome.passed,
                severity=outcome.severity,
                detail=outcome.detail,
                checked_at=checked_at,
            )
        )

    db.commit()

    accepted = not any(
        not outcome.passed and outcome.severity == "reject" for outcome in outcomes
    )

    return QualityGateResult(accepted=accepted, outcomes=outcomes)
