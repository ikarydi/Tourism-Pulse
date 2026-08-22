"""Orchestration for turning one Wikipedia pageviews observation into a
`wikipedia_pageviews` Signal row.

Like YouTube/OSM, this overwrites the place's single current value in
place (keyed on (place_id, signal_type, source)) rather than
accumulating a new row per run: each run re-fetches a fresh trailing
30-day window, so the "signal" is that rolling window's total, not a
period in a published series.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.wikipedia.parser import (
    WIKIPEDIA_SOURCE_NAME,
    WikipediaPageviewsObservation,
)
from tourism_pulse_api.pulse.wikipedia_interest import normalize_wikipedia_pageviews

WIKIPEDIA_PAGEVIEWS_SIGNAL_TYPE = "wikipedia_pageviews"
TARGET_DIMENSION = "demand"


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    article: str
    total_views: int
    normalized_value: float
    target_dimension: str
    daily_views: list[int]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "article": self.article,
            "total_views": self.total_views,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
            "daily_views": self.daily_views,
        }


def build_preview(observation: WikipediaPageviewsObservation) -> IngestionPreview:
    return IngestionPreview(
        source=WIKIPEDIA_SOURCE_NAME,
        article=observation.article,
        total_views=observation.total_views,
        normalized_value=normalize_wikipedia_pageviews(observation.total_views),
        target_dimension=TARGET_DIMENSION,
        daily_views=observation.daily_views,
    )


def upsert_wikipedia_pageviews_signal(
    db: Session,
    *,
    place_id: int,
    observation: WikipediaPageviewsObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, QualityGateResult]:
    """Write (or overwrite) the wikipedia_pageviews Signal for one place,
    after passing it through the data-quality gate (spec section 14).

    Returns (signal, gate). `signal` is None when the gate rejects the
    candidate - the already-archived SourceObservation is left untouched
    either way (spec 12.1), only the Signal write is skipped.
    """
    observed_at = observation.retrieved_at

    gate = run_quality_checks(
        db,
        SignalCandidate(
            place_id=place_id,
            signal_type=WIKIPEDIA_PAGEVIEWS_SIGNAL_TYPE,
            value=Decimal(observation.total_views),
            unit="views",
            observed_at=observed_at,
            source=WIKIPEDIA_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, gate

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == WIKIPEDIA_PAGEVIEWS_SIGNAL_TYPE,
            Signal.source == WIKIPEDIA_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = observation.total_views
        existing.observed_at = observed_at
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, gate

    signal = Signal(
        place_id=place_id,
        signal_type=WIKIPEDIA_PAGEVIEWS_SIGNAL_TYPE,
        value=observation.total_views,
        unit="views",
        observed_at=observed_at,
        source=WIKIPEDIA_SOURCE_NAME,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, gate
