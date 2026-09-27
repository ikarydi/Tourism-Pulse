"""Connects a Pulse calculation to the actual evidence behind it (spec
section 13's governance question "where did it come from?", and the
missing half of `pulse.interpretation`'s output - that module can say
"$Dimension is weak", never *why*).

`build_all_dimension_evidence` reuses infrastructure already built rather
than inventing new queries:

- **Contributing signals**: a reverse lookup of `pulse.signal_adapter.
  DIMENSION_MAP` (which `signal_type`s feed this dimension), filtered
  against the place's already-loaded signals.
- **Related content** (events/risk/economic only): `NewsArticle`/
  `VideoItem` rows whose `categories` include the dimension's name - these
  line up exactly, since `classification.item_classifier.ItemCategory`'s
  values ("events"/"risk"/"economic") *are* the dimension names.
- **Related events** (events dimension only): the place's own `Event` rows.

This is the deterministic half of the insight engine (`pulse/narrative.py`
is the LLM half, built on top of this module's output) - the master
spec's AI/ML architecture section (24) is explicit that the Pulse engine
and its supporting analysis stay deterministic; only the narrative
synthesis is an LLM's job.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.event import Event
from tourism_pulse_api.db.models.news_article import NewsArticle
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.db.models.video_item import VideoItem
from tourism_pulse_api.pulse.calculator import PulseResult
from tourism_pulse_api.pulse.coefficients import DIMENSION_WEIGHTS
from tourism_pulse_api.pulse.engine import PRESSURE_DIMENSION
from tourism_pulse_api.pulse.signal_adapter import DIMENSION_MAP

# Caps keep both the API response and (later) the narrative prompt built
# from it compact - a place with a long ingestion history can have
# hundreds of signals/articles behind one dimension (this project's own
# Eurostat backfill testing produced exactly that), and only the most
# recent handful are ever meaningful evidence for "what's happening now".
_MAX_CONTRIBUTING_SIGNALS = 5
_MAX_RELATED_ITEMS = 3

# Built once at import time: signal_type -> dimension inverted into
# dimension -> {signal_types}.
_SIGNAL_TYPES_BY_DIMENSION: dict[str, set[str]] = {}
for _signal_type, _dimension in DIMENSION_MAP.items():
    _SIGNAL_TYPES_BY_DIMENSION.setdefault(_dimension, set()).add(_signal_type)


@dataclass(frozen=True)
class EvidenceSignal:
    id: int
    signal_type: str
    source: str
    value: float
    unit: str | None
    observed_at: datetime


@dataclass(frozen=True)
class EvidenceArticle:
    title: str
    url: str
    source: str
    published_at: datetime | None


@dataclass(frozen=True)
class EvidenceVideo:
    title: str
    video_id: str
    channel: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class EvidenceEvent:
    id: int
    name: str
    event_type: str
    start_at: datetime


@dataclass(frozen=True)
class DimensionEvidence:
    dimension: str
    value: float
    contributing_signals: list[EvidenceSignal]
    related_articles: list[EvidenceArticle]
    related_videos: list[EvidenceVideo]
    related_events: list[EvidenceEvent]


def _evidence_for_dimension(
    *,
    dimension: str,
    dimension_value: float,
    signals: list[Signal],
    events: list[Event],
    articles: list[NewsArticle],
    videos: list[VideoItem],
) -> DimensionEvidence:
    signal_types = _SIGNAL_TYPES_BY_DIMENSION.get(dimension, set())

    contributing = sorted(
        (
            signal
            for signal in signals
            if signal.signal_type.strip().lower() in signal_types
        ),
        key=lambda signal: signal.observed_at,
        reverse=True,
    )[:_MAX_CONTRIBUTING_SIGNALS]

    related_articles = [
        article for article in articles if dimension in article.categories
    ][:_MAX_RELATED_ITEMS]

    related_videos = [
        video for video in videos if dimension in video.categories
    ][:_MAX_RELATED_ITEMS]

    # Only the events dimension has a natural Event-shaped evidence source
    # - the others have nothing analogous to point at.
    related_events = (
        sorted(events, key=lambda event: event.start_at)[:_MAX_RELATED_ITEMS]
        if dimension == "events"
        else []
    )

    return DimensionEvidence(
        dimension=dimension,
        value=dimension_value,
        contributing_signals=[
            EvidenceSignal(
                id=signal.id,
                signal_type=signal.signal_type,
                source=signal.source,
                value=float(signal.value),
                unit=signal.unit,
                observed_at=signal.observed_at,
            )
            for signal in contributing
        ],
        related_articles=[
            EvidenceArticle(
                title=article.title,
                url=article.url,
                source=article.source,
                published_at=article.published_at,
            )
            for article in related_articles
        ],
        related_videos=[
            EvidenceVideo(
                title=video.title,
                video_id=video.video_id,
                channel=video.channel,
                published_at=video.published_at,
            )
            for video in related_videos
        ],
        related_events=[
            EvidenceEvent(
                id=event.id,
                name=event.name,
                event_type=event.event_type,
                start_at=event.start_at,
            )
            for event in related_events
        ],
    )


def build_all_dimension_evidence(
    db: Session,
    *,
    place_id: int,
    pulse: PulseResult,
    signals: list[Signal],
    events: list[Event],
    pressure: float | None = None,
) -> dict[str, DimensionEvidence]:
    """One `DimensionEvidence` per Pulse dimension (`pulse.coefficients.
    DIMENSION_WEIGHTS`'s 6 keys). `signals`/`events` are the place's
    already-loaded lists (routers/pulse.py loads them once for the whole
    calculation); articles/videos are fetched once here rather than once
    per dimension.
    """
    articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.place_id == place_id)
        .order_by(
            NewsArticle.published_at.desc().nullslast(),
            NewsArticle.id.desc(),
        )
        .all()
    )

    videos = (
        db.query(VideoItem)
        .filter(VideoItem.place_id == place_id)
        .order_by(
            VideoItem.published_at.desc().nullslast(),
            VideoItem.id.desc(),
        )
        .all()
    )

    evidence = {
        dimension: _evidence_for_dimension(
            dimension=dimension,
            dimension_value=getattr(pulse, dimension),
            signals=signals,
            events=events,
            articles=articles,
            videos=videos,
        )
        for dimension in DIMENSION_WEIGHTS
    }

    # The pressure index sits beside the Pulse (pulse.engine.
    # PRESSURE_DIMENSION); it gets evidence only when it has a reading.
    if pressure is not None:
        evidence[PRESSURE_DIMENSION] = _evidence_for_dimension(
            dimension=PRESSURE_DIMENSION,
            dimension_value=pressure,
            signals=signals,
            events=events,
            articles=articles,
            videos=videos,
        )

    return evidence
