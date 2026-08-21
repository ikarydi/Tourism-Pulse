"""Orchestration for turning one YouTube search observation into a
`search_interest` Signal row.

Like OSM's POI-count signal, this overwrites the place's single current
value in place (keyed on (place_id, signal_type, source)) rather than
accumulating a new row per run: a search-result count is "the web as of
now", not a period in a published series, so re-running replaces the
value instead of piling up near-duplicate rows.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.youtube.parser import (
    YOUTUBE_SOURCE_NAME,
    YoutubeSearchObservation,
)
from tourism_pulse_api.pulse.search_interest import normalize_search_interest

SEARCH_INTEREST_SIGNAL_TYPE = "search_interest"
TARGET_DIMENSION = "demand"


@dataclass(frozen=True)
class IngestionPreview:
    source: str
    query: str
    total_results: int
    normalized_value: float
    target_dimension: str
    sample_video_titles: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "query": self.query,
            "total_results": self.total_results,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
            "sample_video_titles": self.sample_video_titles,
        }


def build_preview(observation: YoutubeSearchObservation) -> IngestionPreview:
    return IngestionPreview(
        source=YOUTUBE_SOURCE_NAME,
        query=observation.query,
        total_results=observation.total_results,
        normalized_value=normalize_search_interest(observation.total_results),
        target_dimension=TARGET_DIMENSION,
        sample_video_titles=observation.sample_video_titles,
    )


def upsert_search_interest_signal(
    db: Session,
    *,
    place_id: int,
    observation: YoutubeSearchObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, QualityGateResult]:
    """Write (or overwrite) the search-interest Signal for one place,
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
            signal_type=SEARCH_INTEREST_SIGNAL_TYPE,
            value=Decimal(observation.total_results),
            unit="count",
            observed_at=observed_at,
            source=YOUTUBE_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, gate

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == SEARCH_INTEREST_SIGNAL_TYPE,
            Signal.source == YOUTUBE_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = observation.total_results
        existing.observed_at = observed_at
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, gate

    signal = Signal(
        place_id=place_id,
        signal_type=SEARCH_INTEREST_SIGNAL_TYPE,
        value=observation.total_results,
        unit="count",
        observed_at=observed_at,
        source=YOUTUBE_SOURCE_NAME,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, gate
