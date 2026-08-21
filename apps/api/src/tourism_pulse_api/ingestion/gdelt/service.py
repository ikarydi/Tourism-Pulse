"""Orchestration for turning GDELT observations into Signal rows.

Two independent signal types (see the package docstring for why they're
kept as separate CLI modes/requests). Both overwrite the place's single
current value in place, keyed on (place_id, signal_type, source) - like
OSM's POI count and YouTube's search interest, a news snapshot is "the
web as of now", not a period in a published series.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.gdelt.parser import (
    GDELT_SOURCE_NAME,
    GdeltArticleListObservation,
    GdeltToneObservation,
)
from tourism_pulse_api.pulse.news_mentions import normalize_news_mentions
from tourism_pulse_api.pulse.news_sentiment import normalize_news_tone

NEWS_MENTIONS_SIGNAL_TYPE = "news_mentions"
NEWS_SENTIMENT_SIGNAL_TYPE = "news_sentiment"
TARGET_DIMENSION = "demand"


@dataclass(frozen=True)
class MentionsPreview:
    source: str
    query: str
    article_count: int
    normalized_value: float
    target_dimension: str
    sample_article_titles: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "query": self.query,
            "article_count": self.article_count,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
            "sample_article_titles": self.sample_article_titles,
        }


@dataclass(frozen=True)
class TonePreview:
    source: str
    query: str
    tone: float
    normalized_value: float
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "query": self.query,
            "tone": self.tone,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
        }


def build_mentions_preview(observation: GdeltArticleListObservation) -> MentionsPreview:
    return MentionsPreview(
        source=GDELT_SOURCE_NAME,
        query=observation.query,
        article_count=observation.article_count,
        normalized_value=normalize_news_mentions(observation.article_count),
        target_dimension=TARGET_DIMENSION,
        sample_article_titles=observation.sample_article_titles,
    )


def build_tone_preview(observation: GdeltToneObservation) -> TonePreview:
    return TonePreview(
        source=GDELT_SOURCE_NAME,
        query=observation.query,
        tone=observation.tone,
        normalized_value=normalize_news_tone(observation.tone),
        target_dimension=TARGET_DIMENSION,
    )


def _upsert_overwrite_in_place(
    db: Session,
    *,
    place_id: int,
    signal_type: str,
    value: Decimal,
    unit: str,
    observed_at: datetime,
    source_url: str,
    source_observation_id: int | None,
) -> tuple[Signal | None, QualityGateResult]:
    gate = run_quality_checks(
        db,
        SignalCandidate(
            place_id=place_id,
            signal_type=signal_type,
            value=value,
            unit=unit,
            observed_at=observed_at,
            source=GDELT_SOURCE_NAME,
            source_observation_id=source_observation_id,
        ),
    )

    if not gate.accepted:
        return None, gate

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == signal_type,
            Signal.source == GDELT_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = value
        existing.observed_at = observed_at
        existing.source_url = source_url
        existing.source_observation_id = source_observation_id
        db.commit()
        db.refresh(existing)
        return existing, gate

    signal = Signal(
        place_id=place_id,
        signal_type=signal_type,
        value=value,
        unit=unit,
        observed_at=observed_at,
        source=GDELT_SOURCE_NAME,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal, gate


def upsert_news_mentions_signal(
    db: Session,
    *,
    place_id: int,
    observation: GdeltArticleListObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, QualityGateResult]:
    """Write (or overwrite) the news-mentions Signal for one place, after
    passing it through the data-quality gate (spec section 14).

    Returns (signal, gate). `signal` is None when the gate rejects the
    candidate - the already-archived SourceObservation is left untouched
    either way (spec 12.1), only the Signal write is skipped.
    """
    return _upsert_overwrite_in_place(
        db,
        place_id=place_id,
        signal_type=NEWS_MENTIONS_SIGNAL_TYPE,
        value=Decimal(observation.article_count),
        unit="count",
        observed_at=observation.retrieved_at,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )


def upsert_news_sentiment_signal(
    db: Session,
    *,
    place_id: int,
    observation: GdeltToneObservation,
    source_url: str,
    source_observation_id: int | None = None,
) -> tuple[Signal | None, QualityGateResult]:
    """Write (or overwrite) the news-sentiment Signal for one place, after
    passing it through the data-quality gate (spec section 14).

    Returns (signal, gate). `signal` is None when the gate rejects the
    candidate - the already-archived SourceObservation is left untouched
    either way (spec 12.1), only the Signal write is skipped.
    """
    return _upsert_overwrite_in_place(
        db,
        place_id=place_id,
        signal_type=NEWS_SENTIMENT_SIGNAL_TYPE,
        value=Decimal(str(observation.tone)),
        unit="tone",
        observed_at=observation.observed_at,
        source_url=source_url,
        source_observation_id=source_observation_id,
    )
