"""Orchestration for turning one OpenAQ PM2.5 observation into an
`air_quality_pm25` Signal row.

Like weather, this overwrites the place's single current value in
place (keyed on (place_id, signal_type, source)) rather than
accumulating a new row per run: the latest station reading is a live
snapshot, not a period in a published series.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.openaq.parser import (
    OPENAQ_SOURCE_NAME,
    AirQualityObservation,
)
from tourism_pulse_api.pulse.air_quality import normalize_pm25

AIR_QUALITY_PM25_SIGNAL_TYPE = "air_quality_pm25"
TARGET_DIMENSION = "environment"


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    location_name: str
    pm25_value: float
    pm25_unit: str
    normalized_value: float
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "location_name": self.location_name,
            "pm25_value": self.pm25_value,
            "pm25_unit": self.pm25_unit,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
        }


def build_preview(observation: AirQualityObservation) -> IngestionPreview:
    return IngestionPreview(
        source=OPENAQ_SOURCE_NAME,
        location_name=observation.location_name,
        pm25_value=observation.pm25_value,
        pm25_unit=observation.pm25_unit,
        normalized_value=normalize_pm25(observation.pm25_value),
        target_dimension=TARGET_DIMENSION,
    )


def upsert_air_quality_signal(
    db: Session,
    *,
    place_id: int,
    observation: AirQualityObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, QualityGateResult]:
    """Write (or overwrite) the air_quality_pm25 Signal for one place,
    after passing it through the data-quality gate (spec section 14).

    Returns (signal, gate). `signal` is None when the gate rejects the
    candidate - the already-archived SourceObservation is left untouched
    either way (spec 12.1), only the Signal write is skipped.
    """
    observed_at = observation.observed_at

    gate = run_quality_checks(
        db,
        SignalCandidate(
            place_id=place_id,
            signal_type=AIR_QUALITY_PM25_SIGNAL_TYPE,
            value=Decimal(str(observation.pm25_value)),
            unit=observation.pm25_unit,
            observed_at=observed_at,
            source=OPENAQ_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, gate

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == AIR_QUALITY_PM25_SIGNAL_TYPE,
            Signal.source == OPENAQ_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = observation.pm25_value
        existing.unit = observation.pm25_unit
        existing.observed_at = observed_at
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, gate

    signal = Signal(
        place_id=place_id,
        signal_type=AIR_QUALITY_PM25_SIGNAL_TYPE,
        value=observation.pm25_value,
        unit=observation.pm25_unit,
        observed_at=observed_at,
        source=OPENAQ_SOURCE_NAME,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, gate
