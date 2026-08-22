"""Orchestration for turning one GDACS events observation into a
`disaster_alert_severity` Signal row.

Like weather/OSM/YouTube/Wikipedia, this overwrites the place's single
current value in place (keyed on (place_id, signal_type, source)) rather
than accumulating a new row per run: "the highest current alert level
for this country right now" is a live snapshot, not a period in a
published series.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.gdacs.parser import (
    GDACS_SOURCE_NAME,
    GdacsEventsObservation,
)
from tourism_pulse_api.pulse.disaster_risk import normalize_disaster_alert_severity

DISASTER_ALERT_SEVERITY_SIGNAL_TYPE = "disaster_alert_severity"
TARGET_DIMENSION = "risk"


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    country: str
    max_current_alert_score: float
    normalized_value: float
    target_dimension: str
    current_event_names: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "country": self.country,
            "max_current_alert_score": self.max_current_alert_score,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
            "current_event_names": self.current_event_names,
        }


def build_preview(observation: GdacsEventsObservation) -> IngestionPreview:
    return IngestionPreview(
        source=GDACS_SOURCE_NAME,
        country=observation.country,
        max_current_alert_score=observation.max_current_alert_score,
        normalized_value=normalize_disaster_alert_severity(
            observation.max_current_alert_score
        ),
        target_dimension=TARGET_DIMENSION,
        current_event_names=[
            event.event_name for event in observation.events if event.is_current
        ],
    )


def upsert_disaster_alert_severity_signal(
    db: Session,
    *,
    place_id: int,
    observation: GdacsEventsObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, QualityGateResult]:
    """Write (or overwrite) the disaster_alert_severity Signal for one
    place, after passing it through the data-quality gate (spec section
    14).

    Returns (signal, gate). `signal` is None when the gate rejects the
    candidate - the already-archived SourceObservation is left untouched
    either way (spec 12.1), only the Signal write is skipped.
    """
    observed_at = observation.retrieved_at

    gate = run_quality_checks(
        db,
        SignalCandidate(
            place_id=place_id,
            signal_type=DISASTER_ALERT_SEVERITY_SIGNAL_TYPE,
            value=Decimal(str(observation.max_current_alert_score)),
            unit="alert_score",
            observed_at=observed_at,
            source=GDACS_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, gate

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == DISASTER_ALERT_SEVERITY_SIGNAL_TYPE,
            Signal.source == GDACS_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = observation.max_current_alert_score
        existing.observed_at = observed_at
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, gate

    signal = Signal(
        place_id=place_id,
        signal_type=DISASTER_ALERT_SEVERITY_SIGNAL_TYPE,
        value=observation.max_current_alert_score,
        unit="alert_score",
        observed_at=observed_at,
        source=GDACS_SOURCE_NAME,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, gate
