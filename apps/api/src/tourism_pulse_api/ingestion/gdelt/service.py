"""Orchestration for turning GDELT observations into Signal rows.

Two independent signal types (see the package docstring for why they're
kept as separate CLI modes/requests). Both overwrite the place's single
current value in place, keyed on (place_id, signal_type, source) - like
OSM's POI count and YouTube's search interest, a news snapshot is "the
web as of now", not a period in a published series.

A `--mode mentions` run additionally persists every article as a
NewsArticle row (see `persist_articles`), classified by
classification.item_classifier, and derives up to three more signals -
news_event_mentions / news_risk_mentions / news_economic_mentions (see
`upsert_category_mentions_signals`) - feeding events/risk/economic
respectively. This is what connects "25 articles about Lyon" to more
than just demand: news_mentions only ever says "how many", the
category counts say "how many were about what".
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from tourism_pulse_api.classification.item_classifier import ItemCategory, classify_item
from tourism_pulse_api.data_quality.pipeline import run_quality_checks
from tourism_pulse_api.data_quality.types import QualityGateResult, SignalCandidate
from tourism_pulse_api.db.models.news_article import NewsArticle
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.gdelt.parser import (
    GDELT_SOURCE_NAME,
    GdeltArticleListObservation,
    GdeltToneObservation,
)
from tourism_pulse_api.pulse.news_category_mentions import normalize_news_category_mentions
from tourism_pulse_api.pulse.news_mentions import normalize_news_mentions
from tourism_pulse_api.pulse.news_sentiment import normalize_news_tone

NEWS_MENTIONS_SIGNAL_TYPE = "news_mentions"
NEWS_SENTIMENT_SIGNAL_TYPE = "news_sentiment"
TARGET_DIMENSION = "demand"

# One signal_type/target-dimension pair per classification.item_classifier
# category - see the module docstring.
CATEGORY_SIGNAL_TYPES: dict[ItemCategory, str] = {
    ItemCategory.EVENTS: "news_event_mentions",
    ItemCategory.RISK: "news_risk_mentions",
    ItemCategory.ECONOMIC: "news_economic_mentions",
}
CATEGORY_DIMENSIONS: dict[ItemCategory, str] = {
    ItemCategory.EVENTS: "events",
    ItemCategory.RISK: "risk",
    ItemCategory.ECONOMIC: "economic",
}


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


# --- item-level: NewsArticle rows + per-category mention signals -----------


def persist_articles(
    db: Session,
    *,
    place_id: int,
    observation: GdeltArticleListObservation,
    source_observation_id: int | None,
) -> list[NewsArticle]:
    """Persist every article in `observation` as a NewsArticle row,
    classified by classification.item_classifier - upserted on
    (source, place_id, url) so re-running the same query never
    duplicates a row already seen in an earlier run's overlapping
    timespan, while still giving each place its own row for an article
    that surfaces under more than one place's query (see the model's
    UniqueConstraint comment).
    """
    rows: list[NewsArticle] = []

    for article in observation.articles:
        categories = sorted(category.value for category in classify_item(article.title))

        existing = (
            db.query(NewsArticle)
            .filter(
                NewsArticle.source == GDELT_SOURCE_NAME,
                NewsArticle.place_id == place_id,
                NewsArticle.url == article.url,
            )
            .one_or_none()
        )

        if existing is not None:
            existing.title = article.title
            existing.domain = article.domain
            existing.published_at = article.seendate
            existing.categories = categories
            existing.source_observation_id = source_observation_id
            existing.retrieved_at = observation.retrieved_at
            rows.append(existing)
            continue

        row = NewsArticle(
            place_id=place_id,
            source=GDELT_SOURCE_NAME,
            url=article.url,
            title=article.title,
            domain=article.domain,
            published_at=article.seendate,
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


def count_articles_by_category(articles: list[NewsArticle]) -> dict[ItemCategory, int]:
    counts: dict[ItemCategory, int] = dict.fromkeys(ItemCategory, 0)

    for article in articles:
        for raw_category in article.categories:
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
    articles: list[NewsArticle],
    source_url: str,
    source_observation_id: int | None,
    observed_at: datetime | None = None,
) -> dict[ItemCategory, tuple[Signal | None, QualityGateResult]]:
    """Count `articles` by category and upsert one signal per category
    that has at least one match - a category with zero matches this run
    is left as-is (not zeroed out), the same "no news is not a signal"
    reasoning `ingestion.gdelt.__main__` already applies to the
    aggregate news_mentions count implicitly (a query that returns zero
    articles still writes a real `0` news_mentions value, but a
    category that simply wasn't classified this run isn't a claim that
    it dropped to zero).
    """
    counts = count_articles_by_category(articles)
    resolved_observed_at = observed_at or datetime.now(UTC)

    results: dict[ItemCategory, tuple[Signal | None, QualityGateResult]] = {}

    for category, count in counts.items():
        if count == 0:
            continue

        results[category] = _upsert_overwrite_in_place(
            db,
            place_id=place_id,
            signal_type=CATEGORY_SIGNAL_TYPES[category],
            value=Decimal(count),
            unit="count",
            observed_at=resolved_observed_at,
            source_url=source_url,
            source_observation_id=source_observation_id,
        )

    return results


def build_category_mentions_preview(
    category: ItemCategory, count: int
) -> CategoryMentionsPreview:
    return CategoryMentionsPreview(
        source=GDELT_SOURCE_NAME,
        category=category.value,
        mention_count=count,
        normalized_value=normalize_news_category_mentions(count),
        target_dimension=CATEGORY_DIMENSIONS[category],
    )
