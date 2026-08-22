"""Tests for GET /places/{place_id}/news - read-only, so rows are seeded
directly via the DB session (as ingestion.gdelt.service.persist_articles
would write them), not via API POST."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, NewsArticle, Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.main import app

client = TestClient(app)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_place(db_session) -> Place:
    destination = Destination(country_code="HU", name="News Router Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="News Router Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def make_article(
    db_session,
    place_id: int,
    *,
    url: str,
    title: str = "Test Article",
    categories: list[str] | None = None,
) -> NewsArticle:
    article = NewsArticle(
        place_id=place_id,
        source="gdelt",
        url=url,
        title=title,
        domain="example.com",
        published_at=datetime(2026, 8, 20, tzinfo=UTC),
        categories=categories or [],
        retrieved_at=datetime.now(UTC),
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


def test_place_not_found_returns_404() -> None:
    response = client.get("/places/999999999/news")

    assert response.status_code == 404


def test_returns_empty_list_for_a_place_with_no_articles(test_place) -> None:
    response = client.get(f"/places/{test_place.id}/news")

    assert response.status_code == 200
    assert response.json() == []


def test_returns_articles_for_the_place(db_session, test_place) -> None:
    make_article(db_session, test_place.id, url="https://a/1", title="Budapest Wine Festival")

    response = client.get(f"/places/{test_place.id}/news")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Budapest Wine Festival"
    assert body[0]["place_id"] == test_place.id


def test_category_filter(db_session, test_place) -> None:
    make_article(
        db_session, test_place.id, url="https://a/1", title="Festival", categories=["events"]
    )
    make_article(
        db_session, test_place.id, url="https://a/2", title="Flood warning", categories=["risk"]
    )

    response = client.get(f"/places/{test_place.id}/news?category=risk")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Flood warning"
