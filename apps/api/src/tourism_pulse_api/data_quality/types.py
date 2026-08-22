from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class QualityCheckable(Protocol):
    """The minimal shape every data-quality check (checks.py) can rely
    on, regardless of whether the candidate is a Signal-shaped numeric
    measurement or an Event-shaped scheduled occurrence.

    `value`/`unit` are numeric-measurement-only - `EventCandidate` fixes
    them at `None` via read-only properties, which is exactly what
    already makes the numeric-only checks
    (missing_value/impossible_range/outlier/value-based duplicate) no-op
    cleanly on an Event candidate: they already guard on
    `candidate.value is None` for SignalCandidate's own "value hasn't
    been fetched yet" case, so an Event candidate falls through the
    exact same guard rather than needing an Event-specific branch.

    `check_type`/`recorded_at`/`max_future_skew` are the generalized
    stand-ins for Signal's `signal_type`/`observed_at` (and a
    per-candidate-type future-date tolerance - see EventCandidate's
    docstring for why that can't just reuse SignalCandidate's).
    `SignalCandidate` and `EventCandidate` both implement these as
    properties aliasing their own real fields, so neither call site
    (ingestion/*/service.py's SignalCandidate construction,
    ingestion/events/service.py's EventCandidate construction) needs to
    change field names.

    `has_value` disambiguates two different meanings of `value is None`:
    for a SignalCandidate, that's a real defect (a Signal is
    fundamentally a value-bearing measurement, so a missing one is
    something check_missing_value must reject) - for an EventCandidate,
    `value` is *never* populated, by design (Event has no scalar
    measurement at all), so the exact same `value is None` state is not
    a defect there. `has_value=False` tells check_missing_value to skip
    cleanly instead of rejecting every single event candidate.
    """

    # Declared as read-only properties, not plain attributes: mypy's
    # structural Protocol matching treats a plain attribute annotation
    # as requiring a settable field, which SignalCandidate/EventCandidate
    # (both frozen, and several members implemented as computed
    # properties) can't and shouldn't provide - every implementer only
    # ever needs to be read from here.
    @property
    def place_id(self) -> int: ...

    @property
    def source(self) -> str: ...

    @property
    def source_observation_id(self) -> int | None: ...

    @property
    def value(self) -> Decimal | None: ...

    @property
    def unit(self) -> str | None: ...

    @property
    def has_value(self) -> bool: ...

    @property
    def check_type(self) -> str: ...

    @property
    def recorded_at(self) -> datetime | None: ...

    @property
    def max_future_skew(self) -> timedelta: ...


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

    @property
    def has_value(self) -> bool:
        return True

    @property
    def check_type(self) -> str:
        return self.signal_type

    @property
    def recorded_at(self) -> datetime | None:
        return self.observed_at

    @property
    def max_future_skew(self) -> timedelta:
        # A Signal's observed_at is something that just happened - see
        # checks.check_invalid_date's docstring/_MAX_FUTURE_SKEW.
        return timedelta(hours=1)


@dataclass(frozen=True)
class EventCandidate:
    """An event not yet written to the database, about to pass through
    the (generalized subset of the) quality gate - see
    ingestion.events.service.upsert_event.

    `value`/`unit` are fixed `None` (never real fields) - Event has no
    scalar measurement the way Signal does, so there is nothing for the
    numeric-only checks to range-check/z-score/compare-for-conflict;
    they already no-op correctly via their existing
    `if candidate.value is None` guards (see QualityCheckable's
    docstring), so no Event-specific branches were needed in checks.py.

    `max_future_skew` is a real, deliberate override, not a rename of
    convenience: SignalCandidate's default (1 hour) assumes "this
    happened just now", which is correct for an observation but wrong
    for a scheduled future event - a real upcoming festival announced
    months out would otherwise fail check_invalid_date's future-date
    guard every time. A generous multi-year tolerance instead - the
    check still catches a genuinely nonsensical date (a bad parse
    landing on year 9999), just not a legitimately-far-out real event.
    """

    place_id: int
    event_type: str
    start_at: datetime | None
    source: str
    source_observation_id: int | None = None

    @property
    def value(self) -> None:
        return None

    @property
    def unit(self) -> None:
        return None

    @property
    def has_value(self) -> bool:
        return False

    @property
    def check_type(self) -> str:
        return self.event_type

    @property
    def recorded_at(self) -> datetime | None:
        return self.start_at

    @property
    def max_future_skew(self) -> timedelta:
        return timedelta(days=365 * 3)


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
