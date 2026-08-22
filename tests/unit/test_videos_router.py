"""Tests for GET /places/{place_id}/videos - same reasoning as
test_news_router.py."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, Place, VideoItem
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
    destination = Destination(country_code="HU", name="Videos Router Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Videos Router Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def make_video(
    db_session,
    place_id: int,
    *,
    video_id: str,
    title: str = "Test Video",
    categories: list[str] | None = None,
) -> VideoItem:
    video = VideoItem(
        place_id=place_id,
        source="youtube",
        video_id=video_id,
        title=title,
        channel="Some Channel",
        published_at=datetime(2026, 8, 20, tzinfo=UTC),
        categories=categories or [],
        retrieved_at=datetime.now(UTC),
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_place_not_found_returns_404() -> None:
    response = client.get("/places/999999999/videos")

    assert response.status_code == 404


def test_returns_empty_list_for_a_place_with_no_videos(test_place) -> None:
    response = client.get(f"/places/{test_place.id}/videos")

    assert response.status_code == 200
    assert response.json() == []


def test_returns_videos_for_the_place(db_session, test_place) -> None:
    make_video(db_session, test_place.id, video_id="v1", title="Budapest Wine Festival Recap")

    response = client.get(f"/places/{test_place.id}/videos")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Budapest Wine Festival Recap"
    assert body[0]["place_id"] == test_place.id


def test_category_filter(db_session, test_place) -> None:
    make_video(db_session, test_place.id, video_id="v1", title="Festival", categories=["events"])
    make_video(
        db_session, test_place.id, video_id="v2", title="Flood footage", categories=["risk"]
    )

    response = client.get(f"/places/{test_place.id}/videos?category=risk")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Flood footage"
