from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class SignalCandidate:
    """A signal not yet written to the database, about to pass through
    the quality gate. Mirrors `db.models.Signal`'s fields (minus `id`, an
    identity that doesn't exist until - and unless - the write happens),
    plus `source_observation_id` for lineage.

    `value`/`observed_at` are optional here (unlike on `Signal`, where
    they're required) specifically so `check_missing_value`/
    `check_invalid_date` have something to reject rather than a candidate
    that could never be constructed with the defect in the first place.
    """

    place_id: int
    signal_type: str
    value: Decimal | None
    unit: str | None
    observed_at: datetime | None
    source: str
    source_observation_id: int | None = None


@dataclass(frozen=True)
class QualityCheckOutcome:
    check_name: str
    passed: bool
    # "reject" (blocks the Signal write) or "warn" (recorded, does not
    # block). Only meaningful when passed is False.
    severity: str
    detail: str | None = None


@dataclass(frozen=True)
class QualityGateResult:
    accepted: bool
    outcomes: list[QualityCheckOutcome]
