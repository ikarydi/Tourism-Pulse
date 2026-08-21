"""Orchestration for turning parsed KSH capacity observations into
`accommodation_capacity` Signal rows: which observation(s) to act on, a
preview for --dry-run, and an idempotent upsert into the database.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.ksh_capacity.parser import (
    KSH_SOURCE_NAME,
    KshCapacityObservation,
)
from tourism_pulse_api.pulse.seasonal_normalization import (
    SeasonalNormalizationResult,
    calculate_seasonal_score,
)

ACCOMMODATION_CAPACITY_SIGNAL_TYPE = "accommodation_capacity"
TARGET_DIMENSION = "capacity"


def select_observations(
    observations: list[KshCapacityObservation],
    *,
    month: str | None = None,
    backfill: bool = False,
) -> list[KshCapacityObservation]:
    """Pick which observations an ingestion run should act on.

    - `month="YYYY-MM"` selects exactly that period, if present.
    - `backfill=True` selects every available period.
    - Otherwise, only the single most recent (latest published) period.
    """
    if not observations:
        return []

    ordered = sorted(observations, key=lambda obs: (obs.year, obs.month))

    if month is not None:
        try:
            year_str, month_str = month.split("-", 1)
            target = (int(year_str), int(month_str))
        except ValueError as exc:
            raise ValueError(
                f"--month must be in YYYY-MM format, got {month!r}"
            ) from exc

        return [obs for obs in ordered if (obs.year, obs.month) == target]

    if backfill:
        return ordered

    return [ordered[-1]]


def seasonal_history_for(
    observation: KshCapacityObservation,
    observations: list[KshCapacityObservation],
) -> list[float]:
    """Prior same-calendar-month values, straight from the downloaded series."""
    return [
        float(other.value)
        for other in observations
        if other is not observation
        and other.month == observation.month
        and (other.year, other.month) < (observation.year, observation.month)
    ]


def observed_at_for(observation: KshCapacityObservation) -> datetime:
    """Timestamp stored on the raw Signal row for a KSH capacity observation.

    KSH does not publish a separate release/publication timestamp alongside
    this dataset, so the last day of the reported month (the period end) is
    used as the best available proxy for "when this observation became
    true", at 00:00 UTC.
    """
    return datetime.combine(observation.period_end, time.min, tzinfo=UTC)


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    place_name: str
    period: str
    metric: str
    raw_value: float
    unit: str
    seasonal: SeasonalNormalizationResult
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "place_name": self.place_name,
            "period": self.period,
            "metric": self.metric,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "seasonal_baseline": self.seasonal.baseline,
            "seasonal_ratio": self.seasonal.ratio,
            "normalized_value": self.seasonal.score,
            "normalization_status": self.seasonal.status,
            "target_dimension": self.target_dimension,
        }


def build_preview(
    observation: KshCapacityObservation,
    observations: list[KshCapacityObservation],
) -> IngestionPreview:
    history = seasonal_history_for(observation, observations)
    seasonal = calculate_seasonal_score(float(observation.value), history)

    return IngestionPreview(
        source=KSH_SOURCE_NAME,
        place_name=observation.place_name,
        period=observation.period,
        metric=observation.metric,
        raw_value=float(observation.value),
        unit=observation.unit,
        seasonal=seasonal,
        target_dimension=TARGET_DIMENSION,
    )


def upsert_capacity_signal(
    db: Session,
    *,
    place_id: int,
    observation: KshCapacityObservation,
    source_url: str,
) -> tuple[Signal, bool]:
    """Idempotently write one KSH observation as an `accommodation_capacity` Signal.

    Returns (signal, created). Re-running this with the same observation and
    place is a no-op beyond refreshing the stored value/unit/source_url -
    it never creates a duplicate row for the same
    (place_id, signal_type, observed_at, source).
    """
    observed_at = observed_at_for(observation)

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == ACCOMMODATION_CAPACITY_SIGNAL_TYPE,
            Signal.observed_at == observed_at,
            Signal.source == KSH_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = observation.value
        existing.unit = observation.unit
        existing.source_url = source_url
        db.commit()
        db.refresh(existing)
        return existing, False

    signal = Signal(
        place_id=place_id,
        signal_type=ACCOMMODATION_CAPACITY_SIGNAL_TYPE,
        value=observation.value,
        unit=observation.unit,
        observed_at=observed_at,
        source=KSH_SOURCE_NAME,
        source_url=source_url,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, True
