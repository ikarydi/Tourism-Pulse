"""Tests for GET /places/{place_id}/demographics - same reasoning as
test_news_router.py (read-only, rows seeded directly)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from tourism_pulse_api.db.models import Destination, Place, PlaceDemographics
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
    destination = Destination(country_code="AT", name="Demographics Router Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Demographics Router Test Place",
        place_type="country",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_place_not_found_returns_404() -> None:
    response = client.get("/places/999999999/demographics")

    assert response.status_code == 404


def test_returns_empty_list_for_a_place_with_no_demographics(test_place) -> None:
    response = client.get(f"/places/{test_place.id}/demographics")

    assert response.status_code == 200
    assert response.json() == []


def test_returns_rows_ordered_by_year(db_session, test_place) -> None:
    for year, population in [(2024, 9_158_750), (2022, 8_978_929), (2025, 9_197_213)]:
        row = PlaceDemographics(
            place_id=test_place.id,
            year=year,
            population=population,
            source="eurostat",
            retrieved_at=datetime.now(UTC),
        )
        db_session.add(row)
    db_session.commit()

    response = client.get(f"/places/{test_place.id}/demographics")

    assert response.status_code == 200
    body = response.json()
    assert [row["year"] for row in body] == [2022, 2024, 2025]
    assert body[-1]["population"] == 9_197_213
