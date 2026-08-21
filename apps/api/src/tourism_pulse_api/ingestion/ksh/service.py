"""Orchestration for turning parsed KSH observations into `tourism_nights`
Signal rows: which observation(s) to act on, a preview for --dry-run, and an
idempotent upsert into the database.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.ksh.parser import KSH_SOURCE_NAME, KshObservation
from tourism_pulse_api.pulse.seasonal_normalization import (
    SeasonalNormalizationResult,
    calculate_seasonal_score,
)

TOURISM_NIGHTS_SIGNAL_TYPE = "tourism_nights"
TARGET_DIMENSION = "demand"


def select_observations(
    observations: list[KshObservation],
    *,
    month: str | None = None,
    backfill: bool = False,
) -> list[KshObservation]:
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
    observation: KshObservation,
    observations: list[KshObservation],
) -> list[float]:
    """Prior same-calendar-month totals, straight from the downloaded series."""
    return [
        float(other.total_nights)
        for other in observations
        if other is not observation
        and other.month == observation.month
        and (other.year, other.month) < (observation.year, observation.month)
    ]


def observed_at_for(observation: KshObservation) -> datetime:
    """Timestamp stored on the raw Signal row for a KSH observation.

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
    raw_value: float
    unit: str
    domestic_nights: float
    international_nights: float
    seasonal: SeasonalNormalizationResult
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "place_name": self.place_name,
            "period": self.period,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "domestic_nights": self.domestic_nights,
            "international_nights": self.international_nights,
            "seasonal_baseline": self.seasonal.baseline,
            "seasonal_ratio": self.seasonal.ratio,
            "normalized_value": self.seasonal.score,
            "normalization_status": self.seasonal.status,
            "target_dimension": self.target_dimension,
        }


def build_preview(
    observation: KshObservation,
    observations: list[KshObservation],
) -> IngestionPreview:
    history = seasonal_history_for(observation, observations)
    seasonal = calculate_seasonal_score(float(observation.total_nights), history)

    return IngestionPreview(
        source=KSH_SOURCE_NAME,
        place_name=observation.place_name,
        period=observation.period,
        raw_value=float(observation.total_nights),
        unit=observation.unit,
        domestic_nights=float(observation.domestic_nights),
        international_nights=float(observation.international_nights),
        seasonal=seasonal,
        target_dimension=TARGET_DIMENSION,
    )


def upsert_tourism_nights_signal(
    db: Session,
    *,
    place_id: int,
    observation: KshObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, bool, QualityGateResult]:
    """Idempotently write one KSH observation as a `tourism_nights` Signal,
    after passing it through the data-quality gate (spec section 14).

    Returns (signal, created, gate). `signal` is None and `created` is
    False when the gate rejects the candidate - the already-archived
    SourceObservation (if any) is left untouched either way (spec 12.1),
    only the Signal write is skipped.

    Re-running this with the same observation and place is a no-op beyond
    refreshing the stored value/unit/source_url - it never creates a
    duplicate row for the same (place_id, signal_type, observed_at, source).
    """
    observed_at = observed_at_for(observation)

    gate = run_quality_checks(
        db,
        SignalCandidate(
            place_id=place_id,
            signal_type=TOURISM_NIGHTS_SIGNAL_TYPE,
            value=observation.total_nights,
            unit=observation.unit,
            observed_at=observed_at,
            source=KSH_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, False, gate

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == TOURISM_NIGHTS_SIGNAL_TYPE,
            Signal.observed_at == observed_at,
            Signal.source == KSH_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = observation.total_nights
        existing.unit = observation.unit
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, False, gate

    signal = Signal(
        place_id=place_id,
        signal_type=TOURISM_NIGHTS_SIGNAL_TYPE,
        value=observation.total_nights,
        unit=observation.unit,
        observed_at=observed_at,
        source=KSH_SOURCE_NAME,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, True, gate
