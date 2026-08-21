"""Orchestration for turning parsed Eurostat observations into Signal rows.

Three signal types, each handled differently:

  tourism_nights   Seasonal normalization (pulse.seasonal_normalization),
                    same as KSH - a raw nights count is meaningless without
                    comparing it to the same calendar month in prior years.
                    Feeds `demand` via pulse.seasonal_signal_adapter.

  tourist_arrivals  Raw/archival only - preserved for lineage and the
                    frontend's raw-signal view, but no Pulse dimension is
                    wired to it (nights already drives demand; adding
                    arrivals too would double-count the same underlying
                    tourism activity).

  occupancy_rate    Already a bounded percentage - no seasonal baseline
                    needed, just the generic normalize_percentage pathway
                    (the same convention "hotel_occupancy" already uses).
                    Feeds `demand` too, as a second, independent piece of
                    evidence alongside nights.

  accommodation_capacity_annual  Bed-place counts, published annually
                    rather than monthly. Seasonal normalization same as
                    tourism_nights, but "same calendar month" degenerates to
                    "prior years" since every observation is stamped
                    December. Feeds `capacity` - the same dimension
                    `ingestion.ksh_capacity` already produces for Hungary,
                    but its own signal_type (not KSH's) so it can carry its
                    own, much longer, half-life (see signal_processing.py).

`pulse.seasonal_signal_adapter` normalizes each place against its own
history regardless of source, so a Eurostat-sourced country's demand score
and a KSH-sourced city's demand score both flow through the identical Pulse
Engine pathway with zero engine-level changes for tourism_nights. Only the
raw signal's `unit` differs (Eurostat reports a raw count; KSH reports
thousands) - each place stays internally consistent since normalization
never compares across places.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.eurostat.parser import EUROSTAT_SOURCE_NAME, EurostatObservation
from tourism_pulse_api.pulse.seasonal_normalization import (
    SeasonalNormalizationResult,
    calculate_seasonal_score,
)

TOURISM_NIGHTS_SIGNAL_TYPE = "tourism_nights"
ARRIVALS_SIGNAL_TYPE = "tourist_arrivals"
OCCUPANCY_RATE_SIGNAL_TYPE = "occupancy_rate"
# Deliberately its own signal_type, not KSH's "accommodation_capacity" -
# both feed the identical pulse.seasonal_signal_adapter pathway and the
# same `capacity` dimension, but Eurostat's tour_cap_nat is published
# annually while KSH's is monthly. Reusing the exact same type would also
# reuse KSH's ~30-day half-life, decaying a still-valid annual figure to
# near-zero within a couple of months - see signal_processing.py's
# DEFAULT_HALF_LIFE_HOURS entry for this type.
ACCOMMODATION_CAPACITY_SIGNAL_TYPE = "accommodation_capacity_annual"

DEMAND_DIMENSION = "demand"
CAPACITY_DIMENSION = "capacity"
NO_DIMENSION = "none (raw archival only)"


def select_observations(
    observations: list[EurostatObservation],
    *,
    month: str | None = None,
    backfill: bool = False,
) -> list[EurostatObservation]:
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
    observation: EurostatObservation,
    observations: list[EurostatObservation],
) -> list[float]:
    """Prior same-calendar-month totals, straight from the downloaded series."""
    return [
        float(other.value)
        for other in observations
        if other is not observation
        and other.month == observation.month
        and (other.year, other.month) < (observation.year, observation.month)
    ]


def observed_at_for(observation: EurostatObservation) -> datetime:
    """Timestamp stored on the raw Signal row for a Eurostat observation.

    Eurostat does not publish a separate release timestamp for these
    datasets, so the last day of the reported month (the period end) is
    used, at 00:00 UTC - the same convention as the KSH adapters.
    """
    return datetime.combine(observation.period_end, time.min, tzinfo=UTC)


def _upsert_signal(
    db: Session,
    *,
    place_id: int,
    signal_type: str,
    observation: EurostatObservation,
    source_url: str,
) -> tuple[Signal, bool]:
    observed_at = observed_at_for(observation)

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == signal_type,
            Signal.observed_at == observed_at,
            Signal.source == EUROSTAT_SOURCE_NAME,
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
        signal_type=signal_type,
        value=observation.value,
        unit=observation.unit,
        observed_at=observed_at,
        source=EUROSTAT_SOURCE_NAME,
        source_url=source_url,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, True


# --- tourism_nights: seasonal normalization ---------------------------------


@dataclass(frozen=True)
class SeasonalIngestionPreview:
    source: str
    geo: str
    place_name: str
    period: str
    raw_value: float
    unit: str
    seasonal: SeasonalNormalizationResult
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "geo": self.geo,
            "place_name": self.place_name,
            "period": self.period,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "seasonal_baseline": self.seasonal.baseline,
            "seasonal_ratio": self.seasonal.ratio,
            "normalized_value": self.seasonal.score,
            "normalization_status": self.seasonal.status,
            "target_dimension": self.target_dimension,
        }


def build_preview(
    observation: EurostatObservation,
    observations: list[EurostatObservation],
) -> SeasonalIngestionPreview:
    history = seasonal_history_for(observation, observations)
    seasonal = calculate_seasonal_score(float(observation.value), history)

    return SeasonalIngestionPreview(
        source=EUROSTAT_SOURCE_NAME,
        geo=observation.geo,
        place_name=observation.geo_name,
        period=observation.period,
        raw_value=float(observation.value),
        unit=observation.unit,
        seasonal=seasonal,
        target_dimension=DEMAND_DIMENSION,
    )


def upsert_tourism_nights_signal(
    db: Session,
    *,
    place_id: int,
    observation: EurostatObservation,
    source_url: str,
) -> tuple[Signal, bool]:
    """Idempotently write one Eurostat observation as a `tourism_nights` Signal.

    Returns (signal, created). Re-running this with the same observation and
    place is a no-op beyond refreshing the stored value/unit/source_url - it
    never creates a duplicate row for the same
    (place_id, signal_type, observed_at, source).
    """
    return _upsert_signal(
        db,
        place_id=place_id,
        signal_type=TOURISM_NIGHTS_SIGNAL_TYPE,
        observation=observation,
        source_url=source_url,
    )


# --- accommodation_capacity: seasonal normalization, feeds capacity --------


def build_capacity_preview(
    observation: EurostatObservation,
    observations: list[EurostatObservation],
) -> SeasonalIngestionPreview:
    """Same seasonal-baseline preview as `build_preview`, targeting `capacity`.

    `observations` should be the full downloaded annual series - every
    observation shares month=12 (see `parser._parse_annual_country_series`),
    so "same calendar month" naturally becomes "prior years of this series".
    """
    history = seasonal_history_for(observation, observations)
    seasonal = calculate_seasonal_score(float(observation.value), history)

    return SeasonalIngestionPreview(
        source=EUROSTAT_SOURCE_NAME,
        geo=observation.geo,
        place_name=observation.geo_name,
        period=observation.period,
        raw_value=float(observation.value),
        unit=observation.unit,
        seasonal=seasonal,
        target_dimension=CAPACITY_DIMENSION,
    )


def upsert_capacity_signal(
    db: Session,
    *,
    place_id: int,
    observation: EurostatObservation,
    source_url: str,
) -> tuple[Signal, bool]:
    """Idempotently write one Eurostat observation as an `accommodation_capacity` Signal.

    Same signal_type `ingestion.ksh_capacity` writes for Hungary, so this
    flows through the identical `pulse.seasonal_signal_adapter` pathway with
    zero engine-level changes - only the source ("eurostat" vs "ksh") and
    raw unit (bed-place count either way, but a different absolute scale)
    differ, and normalization never compares across places.
    """
    return _upsert_signal(
        db,
        place_id=place_id,
        signal_type=ACCOMMODATION_CAPACITY_SIGNAL_TYPE,
        observation=observation,
        source_url=source_url,
    )


# --- tourist_arrivals: raw/archival only, no dimension ----------------------


@dataclass(frozen=True)
class RawIngestionPreview:
    source: str
    geo: str
    place_name: str
    period: str
    raw_value: float
    unit: str
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "geo": self.geo,
            "place_name": self.place_name,
            "period": self.period,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "target_dimension": self.target_dimension,
        }


def build_arrivals_preview(observation: EurostatObservation) -> RawIngestionPreview:
    return RawIngestionPreview(
        source=EUROSTAT_SOURCE_NAME,
        geo=observation.geo,
        place_name=observation.geo_name,
        period=observation.period,
        raw_value=float(observation.value),
        unit=observation.unit,
        target_dimension=NO_DIMENSION,
    )


def upsert_arrivals_signal(
    db: Session,
    *,
    place_id: int,
    observation: EurostatObservation,
    source_url: str,
) -> tuple[Signal, bool]:
    """Idempotently write one Eurostat observation as a `tourist_arrivals` Signal.

    Raw/archival only - see the module docstring for why no dimension
    consumes this signal type directly.
    """
    return _upsert_signal(
        db,
        place_id=place_id,
        signal_type=ARRIVALS_SIGNAL_TYPE,
        observation=observation,
        source_url=source_url,
    )


# --- occupancy_rate: direct percentage normalization, feeds demand ---------


@dataclass(frozen=True)
class PercentageIngestionPreview:
    source: str
    geo: str
    place_name: str
    period: str
    raw_value: float
    unit: str
    normalized_value: float
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "geo": self.geo,
            "place_name": self.place_name,
            "period": self.period,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
        }


def build_occupancy_preview(observation: EurostatObservation) -> PercentageIngestionPreview:
    normalized = max(0.0, min(1.0, float(observation.value) / 100.0))

    return PercentageIngestionPreview(
        source=EUROSTAT_SOURCE_NAME,
        geo=observation.geo,
        place_name=observation.geo_name,
        period=observation.period,
        raw_value=float(observation.value),
        unit=observation.unit,
        normalized_value=normalized,
        target_dimension=DEMAND_DIMENSION,
    )


def upsert_occupancy_rate_signal(
    db: Session,
    *,
    place_id: int,
    observation: EurostatObservation,
    source_url: str,
) -> tuple[Signal, bool]:
    """Idempotently write one Eurostat observation as an `occupancy_rate` Signal.

    Flows through the generic normalize_percentage pathway at Pulse
    calculation time - no seasonal baseline needed, since a percentage is
    already directly interpretable regardless of season.
    """
    return _upsert_signal(
        db,
        place_id=place_id,
        signal_type=OCCUPANCY_RATE_SIGNAL_TYPE,
        observation=observation,
        source_url=source_url,
    )
