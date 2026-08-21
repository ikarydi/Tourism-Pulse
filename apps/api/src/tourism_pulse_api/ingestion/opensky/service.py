"""Orchestration for turning one OpenSky airspace snapshot into an
`airport_traffic` Signal row.

Like OSM's POI count and GDELT's news signals, this overwrites the
place's single current value in place (keyed on (place_id, signal_type,
source)) - a live airspace snapshot is "right now", not a period in a
published series.

Counts only airborne aircraft (on_ground=False in the OpenSky response)
within the caller's bounding box, not aircraft parked/taxiing at an
airport - a cleaner proxy for "how much air traffic is currently
connecting to/over this destination" than including grounded aircraft
would be. See pulse.airport_traffic for the normalization caveats
(the raw count scales with bounding box area, which is caller-chosen,
not fixed).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.opensky.parser import (
    OPENSKY_SOURCE_NAME,
    OpenSkyAirspaceObservation,
)
from tourism_pulse_api.pulse.airport_traffic import normalize_airport_traffic

AIRPORT_TRAFFIC_SIGNAL_TYPE = "airport_traffic"
TARGET_DIMENSION = "demand"


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    airborne_count: int
    normalized_value: float
    target_dimension: str
    sample_callsigns: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "airborne_count": self.airborne_count,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
            "sample_callsigns": self.sample_callsigns,
        }


def build_preview(observation: OpenSkyAirspaceObservation) -> IngestionPreview:
    return IngestionPreview(
        source=OPENSKY_SOURCE_NAME,
        airborne_count=observation.airborne_count,
        normalized_value=normalize_airport_traffic(observation.airborne_count),
        target_dimension=TARGET_DIMENSION,
        sample_callsigns=observation.sample_callsigns,
    )


def upsert_airport_traffic_signal(
    db: Session,
    *,
    place_id: int,
    observation: OpenSkyAirspaceObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, QualityGateResult]:
    """Write (or overwrite) the airport-traffic Signal for one place,
    after passing it through the data-quality gate (spec section 14).

    Returns (signal, gate). `signal` is None when the gate rejects the
    candidate - the already-archived SourceObservation is left untouched
    either way (spec 12.1), only the Signal write is skipped.
    """
    observed_at: datetime = observation.retrieved_at

    gate = run_quality_checks(
        db,
        SignalCandidate(
            place_id=place_id,
            signal_type=AIRPORT_TRAFFIC_SIGNAL_TYPE,
            value=Decimal(observation.airborne_count),
            unit="count",
            observed_at=observed_at,
            source=OPENSKY_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, gate

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == AIRPORT_TRAFFIC_SIGNAL_TYPE,
            Signal.source == OPENSKY_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = observation.airborne_count
        existing.observed_at = observed_at
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, gate

    signal = Signal(
        place_id=place_id,
        signal_type=AIRPORT_TRAFFIC_SIGNAL_TYPE,
        value=observation.airborne_count,
        unit="count",
        observed_at=observed_at,
        source=OPENSKY_SOURCE_NAME,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, gate
