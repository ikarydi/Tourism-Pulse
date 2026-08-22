"""Tests for GDELT's item-level path: persisting each article as a
NewsArticle row, classifying it, and deriving per-category signals -
the "25 articles about Lyon has to be measured, connected to the rest
of the dimensions" piece."""

from datetime import UTC, datetime

import pytest
from tourism_pulse_api.classification.item_classifier import ItemCategory
from tourism_pulse_api.db.models import Destination, NewsArticle, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.gdelt.parser import GdeltArticle, GdeltArticleListObservation
from tourism_pulse_api.ingestion.gdelt.service import (
    build_category_mentions_preview,
    count_articles_by_category,
    persist_articles,
    upsert_category_mentions_signals,
)


def make_article(
    title: str,
    *,
    url: str = "https://example.com/a",
    domain: str = "example.com",
    seendate: datetime | None = None,
    language: str = "English",
) -> GdeltArticle:
    return GdeltArticle(url=url, title=title, domain=domain, seendate=seendate, language=language)


def make_observation(
    articles: list[GdeltArticle], *, query: str = "Budapest"
) -> GdeltArticleListObservation:
    return GdeltArticleListObservation(
        query=query,
        article_count=len(articles),
        retrieved_at=datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
        sample_article_titles=[a.title for a in articles[:5]],
        articles=articles,
    )


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="GDELT Item Level Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="GDELT Item Level Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


# --- persist_articles ---------------------------------------------------------


def test_persist_articles_creates_one_row_per_article(db_session, test_place) -> None:
    observation = make_observation(
        [
            make_article("Budapest Wine Festival returns", url="https://a/1"),
            make_article("Wildfire forces evacuation nearby", url="https://a/2"),
            make_article("Budapest Travel Guide", url="https://a/3"),
        ]
    )

    rows = persist_articles(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    assert len(rows) == 3
    assert all(isinstance(row, NewsArticle) for row in rows)
    assert (
        db_session.query(NewsArticle).filter(NewsArticle.place_id == test_place.id).count() == 3
    )


def test_persist_articles_tags_categories(db_session, test_place) -> None:
    observation = make_observation(
        [make_article("Wildfire forces evacuation nearby", url="https://a/1")]
    )

    rows = persist_articles(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    assert rows[0].categories == ["risk"]


def test_persist_articles_uncategorized_gets_empty_list(db_session, test_place) -> None:
    observation = make_observation([make_article("Budapest Travel Guide", url="https://a/1")])

    rows = persist_articles(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    assert rows[0].categories == []


def test_persist_articles_upserts_on_url_rather_than_duplicating(db_session, test_place) -> None:
    first_observation = make_observation(
        [make_article("Budapest Wine Festival returns", url="https://a/1")]
    )
    persist_articles(
        db_session,
        place_id=test_place.id,
        observation=first_observation,
        source_observation_id=None,
    )

    second_observation = make_observation(
        [make_article("Budapest Wine Festival - updated headline", url="https://a/1")]
    )
    rows = persist_articles(
        db_session,
        place_id=test_place.id,
        observation=second_observation,
        source_observation_id=None,
    )

    assert len(rows) == 1
    assert rows[0].title == "Budapest Wine Festival - updated headline"
    assert (
        db_session.query(NewsArticle)
        .filter(NewsArticle.place_id == test_place.id)
        .count()
        == 1
    )


# --- count_articles_by_category / upsert_category_mentions_signals ------------


def test_count_articles_by_category(db_session, test_place) -> None:
    observation = make_observation(
        [
            make_article("Budapest Wine Festival returns", url="https://a/1"),
            make_article("Budapest Jazz Festival opens", url="https://a/2"),
            make_article("Wildfire forces evacuation nearby", url="https://a/3"),
            make_article("Budapest Travel Guide", url="https://a/4"),
        ]
    )
    rows = persist_articles(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    counts = count_articles_by_category(rows)

    assert counts[ItemCategory.EVENTS] == 2
    assert counts[ItemCategory.RISK] == 1
    assert counts[ItemCategory.ECONOMIC] == 0


def test_upsert_category_mentions_signals_only_writes_nonzero_categories(
    db_session, test_place
) -> None:
    observation = make_observation(
        [make_article("Budapest Wine Festival returns", url="https://a/1")]
    )
    rows = persist_articles(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    results = upsert_category_mentions_signals(
        db_session,
        place_id=test_place.id,
        articles=rows,
        source_url="https://a",
        source_observation_id=None,
    )

    assert ItemCategory.EVENTS in results
    assert ItemCategory.RISK not in results
    assert ItemCategory.ECONOMIC not in results

    event_signal, gate = results[ItemCategory.EVENTS]
    assert gate.accepted is True
    assert event_signal.signal_type == "news_event_mentions"
    assert event_signal.value == 1


def test_upsert_category_mentions_signals_is_idempotent(db_session, test_place) -> None:
    observation = make_observation(
        [
            make_article("Budapest Wine Festival returns", url="https://a/1"),
            make_article("Budapest Jazz Festival opens", url="https://a/2"),
        ]
    )
    rows = persist_articles(
        db_session, place_id=test_place.id, observation=observation, source_observation_id=None
    )

    first_results = upsert_category_mentions_signals(
        db_session,
        place_id=test_place.id,
        articles=rows,
        source_url="https://a",
        source_observation_id=None,
    )
    second_results = upsert_category_mentions_signals(
        db_session,
        place_id=test_place.id,
        articles=rows,
        source_url="https://b",
        source_observation_id=None,
    )

    first_signal, _ = first_results[ItemCategory.EVENTS]
    second_signal, _ = second_results[ItemCategory.EVENTS]

    assert first_signal.id == second_signal.id
    assert (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.signal_type == "news_event_mentions")
        .count()
        == 1
    )


def test_build_category_mentions_preview() -> None:
    preview = build_category_mentions_preview(ItemCategory.RISK, 5)

    assert preview.target_dimension == "risk"
    assert preview.mention_count == 5
    assert 0.0 < preview.normalized_value <= 1.0
