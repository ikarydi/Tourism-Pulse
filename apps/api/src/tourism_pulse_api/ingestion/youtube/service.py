"""Orchestration for turning one YouTube search observation into a
`search_interest` Signal row.

Like OSM's POI-count signal, this overwrites the place's single current
value in place (keyed on (place_id, signal_type, source)) rather than
accumulating a new row per run: a search-result count is "the web as of
now", not a period in a published series, so re-running replaces the
value instead of piling up near-duplicate rows.

Every run additionally persists each returned video as a VideoItem row
(see `persist_videos`), classified by classification.item_classifier,
and derives up to three more signals - video_event_mentions/
video_risk_mentions/video_economic_mentions (see
`upsert_category_mentions_signals`) - the video counterpart to GDELT's
per-category news signals (see ingestion.gdelt.service's module
docstring for the same reasoning).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.classification.item_classifier import ItemCategory, classify_item
from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.db.models.video_item import VideoItem
from tourism_pulse_api.ingestion.youtube.parser import (
    YOUTUBE_SOURCE_NAME,
    YoutubeSearchObservation,
)
from tourism_pulse_api.pulse.search_interest import normalize_search_interest
from tourism_pulse_api.pulse.video_category_mentions import normalize_video_category_mentions

SEARCH_INTEREST_SIGNAL_TYPE = "search_interest"
TARGET_DIMENSION = "demand"

CATEGORY_SIGNAL_TYPES: dict[ItemCategory, str] = {
    ItemCategory.EVENTS: "video_event_mentions",
    ItemCategory.RISK: "video_risk_mentions",
    ItemCategory.ECONOMIC: "video_economic_mentions",
}
CATEGORY_DIMENSIONS: dict[ItemCategory, str] = {
    ItemCategory.EVENTS: "events",
    ItemCategory.RISK: "risk",
    ItemCategory.ECONOMIC: "economic",
}


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


# --- item-level: VideoItem rows + per-category mention signals -------------


def persist_videos(
    db: Session,
    *,
    place_id: int,
    observation: YoutubeSearchObservation,
    source_observation_id: int | None,
) -> list[VideoItem]:
    """Persist every video in `observation` as a VideoItem row,
    classified by classification.item_classifier - upserted on
    (source, place_id, video_id), same reasoning as
    ingestion.gdelt.service.persist_articles.
    """
    rows: list[VideoItem] = []

    for video in observation.videos:
        categories = sorted(category.value for category in classify_item(video.title))

        existing = (
            db.query(VideoItem)
            .filter(
                VideoItem.source == YOUTUBE_SOURCE_NAME,
                VideoItem.place_id == place_id,
                VideoItem.video_id == video.video_id,
            )
            .one_or_none()
        )

        if existing is not None:
            existing.title = video.title
            existing.channel = video.channel
            existing.published_at = video.published_at
            existing.categories = categories
            existing.source_observation_id = source_observation_id
            existing.retrieved_at = observation.retrieved_at
            rows.append(existing)
            continue

        row = VideoItem(
            place_id=place_id,
            source=YOUTUBE_SOURCE_NAME,
            video_id=video.video_id,
            title=video.title,
            channel=video.channel,
            published_at=video.published_at,
            categories=categories,
            source_observation_id=source_observation_id,
            retrieved_at=observation.retrieved_at,
        )
        db.add(row)
        rows.append(row)

    db.commit()

    for row in rows:
        db.refresh(row)

    return rows


@dataclass(frozen=True)
class CategoryMentionsPreview:
    source: str
    category: str
    mention_count: int
    normalized_value: float
    target_dimension: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "category": self.category,
            "mention_count": self.mention_count,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
        }


def count_videos_by_category(videos: list[VideoItem]) -> dict[ItemCategory, int]:
    counts: dict[ItemCategory, int] = dict.fromkeys(ItemCategory, 0)

    for video in videos:
        for raw_category in video.categories:
            try:
                category = ItemCategory(raw_category)
            except ValueError:
                continue
            counts[category] += 1

    return counts


def upsert_category_mentions_signals(
    db: Session,
    *,
    place_id: int,
    videos: list[VideoItem],
    source_url: str,
    source_observation_id: int | None,
    observed_at: datetime | None = None,
) -> dict[ItemCategory, tuple[Signal | None, QualityGateResult]]:
    """Count `videos` by category and upsert one signal per category
    that has at least one match - same "don't zero out a category that
    simply wasn't seen this run" reasoning as
    ingestion.gdelt.service.upsert_category_mentions_signals.
    """
    counts = count_videos_by_category(videos)
    resolved_observed_at = observed_at or datetime.now(UTC)

    results: dict[ItemCategory, tuple[Signal | None, QualityGateResult]] = {}

    for category, count in counts.items():
        if count == 0:
            continue

        signal_type = CATEGORY_SIGNAL_TYPES[category]

        gate = run_quality_checks(
            db,
            SignalCandidate(
                place_id=place_id,
                signal_type=signal_type,
                value=Decimal(count),
                unit="count",
                observed_at=resolved_observed_at,
                source=YOUTUBE_SOURCE_NAME,
                source_observation_id=source_observation_id,
            ),
        )

        if not gate.accepted:
            results[category] = (None, gate)
            continue

        existing = (
            db.query(Signal)
            .filter(
                Signal.place_id == place_id,
                Signal.signal_type == signal_type,
                Signal.source == YOUTUBE_SOURCE_NAME,
            )
            .one_or_none()
        )

        if existing is not None:
            existing.value = count
            existing.observed_at = resolved_observed_at
            existing.source_url = source_url
            existing.source_observation_id = source_observation_id
            db.commit()
            db.refresh(existing)
            results[category] = (existing, gate)
            continue

        signal = Signal(
            place_id=place_id,
            signal_type=signal_type,
            value=count,
            unit="count",
            observed_at=resolved_observed_at,
            source=YOUTUBE_SOURCE_NAME,
            source_url=source_url,
            source_observation_id=source_observation_id,
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        results[category] = (signal, gate)

    return results


def build_category_mentions_preview(
    category: ItemCategory, count: int
) -> CategoryMentionsPreview:
    return CategoryMentionsPreview(
        source=YOUTUBE_SOURCE_NAME,
        category=category.value,
        mention_count=count,
        normalized_value=normalize_video_category_mentions(count),
        target_dimension=CATEGORY_DIMENSIONS[category],
    )
