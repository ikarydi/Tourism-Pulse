"""Individual data-quality checks (spec section 14).

Each check takes a `QualityCheckable` (plus a `Session`/`now` where it
needs one) and returns a `QualityCheckOutcome`. `data_quality.pipeline`
runs the full set and persists one `DataQualityResult` row per outcome.
`QualityCheckable` is a Protocol both `SignalCandidate` and
`EventCandidate` satisfy - see data_quality.types for why the numeric-
only checks below (missing_value/impossible_range/outlier/value-based
duplicate) already no-op correctly for an Event candidate without any
Event-specific branches here.

Two spec-14 checks are deliberately not here: `check_source_failure` and
`check_schema_change` are about one *fetch*, not one *candidate signal* -
they belong at the archive boundary (alongside `archive_raw_observation`),
not in the per-signal gate this module implements. `inconsistent_totals`
(the tenth spec-14 category) is out of scope this round: no current
adapter emits the kind of multi-field totals (e.g. domestic + international
= total nights) that check would compare.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.types import QualityCheckable, QualityCheckOutcome
from tourism_pulse_api.db.models.signal import Signal

# (min, max) per signal_type; max=None means "no upper bound, just >= min".
# Signal types absent from this table have no impossible-range check
# applied (there is nothing yet known to bound them by) rather than being
# rejected outright.
IMPOSSIBLE_RANGE_BOUNDS: dict[str, tuple[float, float | None]] = {
    "weather_comfort": (0.0, 100.0),
    "occupancy_rate": (0.0, 100.0),
    "hotel_occupancy": (0.0, 100.0),
    "humidity": (0.0, 100.0),
    "temperature": (-90.0, 60.0),
    "precipitation": (0.0, 500.0),
    "wind_speed": (0.0, 500.0),
    "tourism_nights": (0.0, None),
    "accommodation_capacity": (0.0, None),
    "accommodation_capacity_annual": (0.0, None),
    "tourist_arrivals": (0.0, None),
    "hotel_count": (0.0, None),
    "restaurant_count": (0.0, None),
    "search_interest": (0.0, None),
    "wikipedia_pageviews": (0.0, None),
    # GDACS alertscore tops out around 3 (Red); a generous upper bound
    # in case an unusually extreme episode-level score exceeds it.
    "disaster_alert_severity": (0.0, 10.0),
    # PM2.5 concentration, µg/m3 - a generous ceiling above even extreme
    # wildfire-smoke episodes.
    "air_quality_pm25": (0.0, 1000.0),
    # Year-over-year % change - can be negative (a shrinking sector); a
    # generous +/-500% ceiling well beyond any plausible real swing.
    "tourism_turnover_growth": (-500.0, 500.0),
    # HICP annual rates of change, percent (see ingestion.eurostat_bulk).
    "price_change_all": (-100.0, 1000.0),
    "price_change_accommodation": (-100.0, 1000.0),
    "price_change_restaurants": (-100.0, 1000.0),
    "price_change_air_fares": (-100.0, 1000.0),
    # Nights-per-resident ratio - always >= 0, no natural upper bound.
    "visitor_pressure": (0.0, None),
    # Per-category item counts - always >= 0, no natural upper bound.
    "news_event_mentions": (0.0, None),
    "news_risk_mentions": (0.0, None),
    "news_economic_mentions": (0.0, None),
    "video_event_mentions": (0.0, None),
    "video_risk_mentions": (0.0, None),
    "video_economic_mentions": (0.0, None),
    "news_mentions": (0.0, None),
    # GDELT's documented theoretical tone range.
    "news_sentiment": (-100.0, 100.0),
    "airport_traffic": (0.0, None),
}

# Staleness threshold in days per signal_type, mirroring the reasoning in
# pulse.signal_processing.DEFAULT_HALF_LIFE_HOURS (publish cadence) but
# kept independent - this check must also cover raw-archival-only signal
# types (e.g. weather's raw readings) that never reach the Pulse engine
# and so have no half-life entry there at all.
STALE_THRESHOLD_DAYS: dict[str, int] = {
    "weather_comfort": 2,
    "temperature": 2,
    "humidity": 2,
    "precipitation": 2,
    "wind_speed": 2,
    "hotel_count": 120,
    "restaurant_count": 120,
    "tourism_nights": 60,
    "accommodation_capacity": 60,
    "occupancy_rate": 60,
    "tourist_arrivals": 60,
    "accommodation_capacity_annual": 400,
    "search_interest": 30,
    "wikipedia_pageviews": 30,
    "news_mentions": 14,
    "news_sentiment": 14,
    "airport_traffic": 1,
    # GDACS refreshes every ~6 minutes - a live-alert source like
    # airport_traffic, not a periodic statistical release.
    "disaster_alert_severity": 1,
    # Same cadence tier as weather - air quality changes fast.
    "air_quality_pm25": 2,
    # Annual figures, same tier as accommodation_capacity_annual.
    "tourism_turnover_growth": 400,
    "visitor_pressure": 60,
    # Same cadence tier as their aggregate counterparts.
    "news_event_mentions": 14,
    "news_risk_mentions": 14,
    "news_economic_mentions": 14,
    "video_event_mentions": 30,
    "video_risk_mentions": 30,
    "video_economic_mentions": 30,
}
DEFAULT_STALE_THRESHOLD_DAYS = 30

# Below this, an outlier check has too little history to mean anything.
_MIN_OUTLIER_HISTORY = 3
_OUTLIER_Z_SCORE_THRESHOLD = 3.0

_EARLIEST_PLAUSIBLE_OBSERVED_AT = datetime(1900, 1, 1, tzinfo=UTC)


def _pass(check_name: str) -> QualityCheckOutcome:
    return QualityCheckOutcome(check_name=check_name, passed=True, severity="reject")


def check_missing_value(candidate: QualityCheckable) -> QualityCheckOutcome:
    # has_value=False (EventCandidate) means "this candidate type never
    # carries a scalar value" - structural, not a defect. Only a
    # candidate type that's supposed to have one (has_value=True) can
    # fail this check by having value=None.
    if not candidate.has_value:
        return _pass("missing_value")

    if candidate.value is None:
        return QualityCheckOutcome(
            check_name="missing_value",
            passed=False,
            severity="reject",
            detail="value is missing",
        )

    return _pass("missing_value")


def check_invalid_unit(candidate: QualityCheckable) -> QualityCheckOutcome:
    # unit is legitimately nullable on Signal itself (not every signal
    # needs one) - only an empty/whitespace string, which usually means a
    # caller passed "" rather than omitting the field, is flagged.
    if candidate.unit is not None and not candidate.unit.strip():
        return QualityCheckOutcome(
            check_name="invalid_unit",
            passed=False,
            severity="warn",
            detail="unit is an empty/whitespace string",
        )

    return _pass("invalid_unit")


def check_invalid_date(
    candidate: QualityCheckable,
    *,
    now: datetime | None = None,
) -> QualityCheckOutcome:
    if candidate.recorded_at is None:
        return QualityCheckOutcome(
            check_name="invalid_date",
            passed=False,
            severity="reject",
            detail="recorded_at is missing",
        )

    recorded_at = candidate.recorded_at
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=UTC)

    reference_now = now or datetime.now(UTC)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=UTC)

    if recorded_at > reference_now + candidate.max_future_skew:
        return QualityCheckOutcome(
            check_name="invalid_date",
            passed=False,
            severity="reject",
            detail=f"recorded_at {recorded_at.isoformat()} is too far in the future",
        )

    if recorded_at < _EARLIEST_PLAUSIBLE_OBSERVED_AT:
        return QualityCheckOutcome(
            check_name="invalid_date",
            passed=False,
            severity="reject",
            detail=f"recorded_at {recorded_at.isoformat()} is implausibly old",
        )

    return _pass("invalid_date")


def check_impossible_range(candidate: QualityCheckable) -> QualityCheckOutcome:
    if candidate.value is None:
        # check_missing_value is the authoritative record of this defect.
        return _pass("impossible_range")

    bounds = IMPOSSIBLE_RANGE_BOUNDS.get(candidate.check_type.strip().lower())
    if bounds is None:
        return _pass("impossible_range")

    min_value, max_value = bounds
    value = float(candidate.value)

    if value < min_value or (max_value is not None and value > max_value):
        upper = "no upper bound" if max_value is None else str(max_value)
        return QualityCheckOutcome(
            check_name="impossible_range",
            passed=False,
            severity="reject",
            detail=f"value {value} outside expected range [{min_value}, {upper}]",
        )

    return _pass("impossible_range")


def check_duplicate(db: Session, candidate: QualityCheckable) -> QualityCheckOutcome:
    # Queries the Signal table specifically - a real Signal-only check
    # (Event's natural key is source+external_id, not place+type+
    # observed_at+source, and Event has no value to conflict over
    # anyway). Already no-ops correctly for an Event candidate via this
    # same guard, since EventCandidate.value is always None - see
    # QualityCheckable's docstring.
    if candidate.recorded_at is None or candidate.value is None:
        return _pass("duplicate")

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == candidate.place_id,
            Signal.signal_type == candidate.check_type,
            Signal.observed_at == candidate.recorded_at,
            Signal.source == candidate.source,
        )
        .one_or_none()
    )

    if existing is not None and existing.value != candidate.value:
        # A true duplicate (identical value) is a harmless no-op via
        # upsert. A conflicting value at the same natural key is worth
        # flagging, but not blocking - the source may simply be
        # correcting itself, and a reject here would break legitimate
        # updates.
        return QualityCheckOutcome(
            check_name="duplicate",
            passed=False,
            severity="warn",
            detail=(f"existing signal has value {existing.value}, candidate has {candidate.value}"),
        )

    return _pass("duplicate")


def check_outlier(db: Session, candidate: QualityCheckable) -> QualityCheckOutcome:
    # Same Signal-only reasoning as check_duplicate above - already
    # no-ops for an Event candidate (value is always None) via this guard.
    if candidate.value is None:
        return _pass("outlier")

    history = [
        float(value)
        for (value,) in db.query(Signal.value)
        .filter(
            Signal.place_id == candidate.place_id,
            Signal.signal_type == candidate.check_type,
        )
        .all()
    ]

    if len(history) < _MIN_OUTLIER_HISTORY:
        return _pass("outlier")

    mean = sum(history) / len(history)
    variance = sum((v - mean) ** 2 for v in history) / len(history)
    stdev = variance**0.5

    if stdev == 0:
        return _pass("outlier")

    z_score = abs(float(candidate.value) - mean) / stdev

    if z_score > _OUTLIER_Z_SCORE_THRESHOLD:
        return QualityCheckOutcome(
            check_name="outlier",
            passed=False,
            severity="warn",
            detail=(
                f"value {candidate.value} is {z_score:.1f} standard "
                f"deviations from this place's history for "
                f"{candidate.check_type} (mean {mean:.2f})"
            ),
        )

    return _pass("outlier")


def check_stale(
    candidate: QualityCheckable,
    *,
    now: datetime | None = None,
) -> QualityCheckOutcome:
    if candidate.recorded_at is None:
        # check_invalid_date is the authoritative record of this defect.
        return _pass("stale")

    recorded_at = candidate.recorded_at
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=UTC)

    reference_now = now or datetime.now(UTC)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=UTC)

    # For an Event candidate, recorded_at is start_at - usually still in
    # the future, giving a negative age that never trips this check
    # (correctly: an upcoming event isn't "stale"). A past event past
    # the threshold still warns, which is a reasonable heads-up, not a
    # defect worth special-casing away.
    age_days = (reference_now - recorded_at).days
    threshold = STALE_THRESHOLD_DAYS.get(
        candidate.check_type.strip().lower(),
        DEFAULT_STALE_THRESHOLD_DAYS,
    )

    if age_days > threshold:
        return QualityCheckOutcome(
            check_name="stale",
            passed=False,
            severity="warn",
            detail=f"{age_days} days old, exceeds {threshold}-day threshold",
        )

    return _pass("stale")


# --- archive-boundary checks (about one fetch, not one candidate) --------


def check_source_failure(raw_payload: str) -> QualityCheckOutcome:
    if not raw_payload.strip():
        return QualityCheckOutcome(
            check_name="source_failure",
            passed=False,
            severity="reject",
            detail="fetched payload is empty",
        )

    return _pass("source_failure")


def check_schema_change(
    db: Session,
    *,
    source_id: int,
    dataset: str,
    schema_version: str | None,
) -> QualityCheckOutcome:
    if schema_version is None:
        return _pass("schema_change")

    from tourism_pulse_api.db.models.source_observation import SourceObservation

    previous_version = (
        db.query(SourceObservation.schema_version)
        .filter(
            SourceObservation.source_id == source_id,
            SourceObservation.dataset == dataset,
            SourceObservation.schema_version.isnot(None),
        )
        .order_by(SourceObservation.retrieved_at.desc())
        .limit(1)
        .scalar()
    )

    if previous_version is not None and previous_version != schema_version:
        return QualityCheckOutcome(
            check_name="schema_change",
            passed=False,
            severity="warn",
            detail=f"schema_version changed from {previous_version!r} to {schema_version!r}",
        )

    return _pass("schema_change")


__all__ = [
    "IMPOSSIBLE_RANGE_BOUNDS",
    "STALE_THRESHOLD_DAYS",
    "check_duplicate",
    "check_impossible_range",
    "check_invalid_date",
    "check_invalid_unit",
    "check_missing_value",
    "check_outlier",
    "check_schema_change",
    "check_source_failure",
    "check_stale",
]
