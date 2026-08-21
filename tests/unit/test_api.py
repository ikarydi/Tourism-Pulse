from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tourism_pulse_api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_destination() -> None:
    create_response = client.post(
        "/destinations",
        json={
            "country_code": "GR",
            "name": "Test Athens",
        },
    )

    assert create_response.status_code == 201

    destination = create_response.json()

    assert destination["country_code"] == "GR"
    assert destination["name"] == "Test Athens"
    assert isinstance(destination["id"], int)

    list_response = client.get("/destinations")

    assert list_response.status_code == 200

    destinations = list_response.json()

    assert any(
        item["id"] == destination["id"]
        and item["country_code"] == "GR"
        and item["name"] == "Test Athens"
        for item in destinations
    )

def test_create_and_list_places() -> None:
    destination_response = client.post(
        "/destinations",
        json={
            "country_code": "GR",
            "name": "Test Place Destination",
        },
    )

    assert destination_response.status_code == 201

    destination_id = destination_response.json()["id"]

    create_response = client.post(
        f"/destinations/{destination_id}/places",
        json={
            "name": "Acropolis",
            "place_type": "landmark",
        },
    )

    assert create_response.status_code == 201

    place = create_response.json()

    assert place["name"] == "Acropolis"
    assert place["place_type"] == "landmark"
    assert place["destination_id"] == destination_id
    assert isinstance(place["id"], int)

    list_response = client.get(
        f"/destinations/{destination_id}/places",
    )

    assert list_response.status_code == 200

    places = list_response.json()

    assert any(
        item["id"] == place["id"]
        and item["destination_id"] == destination_id
        and item["name"] == "Acropolis"
        for item in places
    )


def test_get_place() -> None:
    destination_response = client.post(
        "/destinations",
        json={
            "country_code": "GR",
            "name": "Test Direct Place",
        },
    )

    assert destination_response.status_code == 201

    destination_id = destination_response.json()["id"]

    create_response = client.post(
        f"/destinations/{destination_id}/places",
        json={
            "name": "Parthenon",
            "place_type": "monument",
        },
    )

    assert create_response.status_code == 201

    place_id = create_response.json()["id"]

    response = client.get(f"/places/{place_id}")

    assert response.status_code == 200

    place = response.json()

    assert place["id"] == place_id
    assert place["destination_id"] == destination_id
    assert place["name"] == "Parthenon"
    assert place["place_type"] == "monument"
    # Coordinates aren't settable via this endpoint (backfilled separately
    # for the map view - see infrastructure/), so a freshly created place
    # has none yet.
    assert place["latitude"] is None
    assert place["longitude"] is None


def test_place_not_found() -> None:
    response = client.get("/places/999999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Place not found"}
def test_calculate_place_pulse() -> None:
    destination_response = client.post(
        "/destinations",
        json={
            "country_code": "HU",
            "name": "Test Budapest",
        },
    )

    assert destination_response.status_code == 201

    destination_id = destination_response.json()["id"]

    place_response = client.post(
        f"/destinations/{destination_id}/places",
        json={
            "name": "Budapest",
            "place_type": "destination",
        },
    )

    assert place_response.status_code == 201

    place_id = place_response.json()["id"]

    signals = [
    {
        "signal_type": "occupancy",
        "value": 80,
        "unit": "percent",
        "observed_at": "2026-08-20T10:00:00Z",
        "source": "government",
    },
    {
        "signal_type": "hotel_occupancy",
        "value": 70,
        "unit": "percent",
        "observed_at": "2026-08-20T10:00:00Z",
        "source": "official",
    },
    {
        "signal_type": "sentiment",
        "value": 0.8,
        "unit": "score",
        "observed_at": "2026-08-20T10:00:00Z",
        "source": "commercial",
    },
    {
        "signal_type": "weather_comfort",
        "value": 85,
        "unit": "percent",
        "observed_at": "2026-08-20T10:00:00Z",
        "source": "government",
    },
]

    for signal in signals:
        response = client.post(
            f"/places/{place_id}/signals",
            json=signal,
        )

        assert response.status_code == 201

    response = client.get(
        f"/places/{place_id}/pulse",
    )

    assert response.status_code == 200

    pulse = response.json()

    print("\nTOURISM PULSE RESULT")
    print(pulse)

    assert pulse["place_id"] == place_id
    assert 0.0 <= pulse["pulse"] <= 100.0

    assert 0.0 <= pulse["dimensions"]["demand"] <= 100.0
    assert 0.0 <= pulse["dimensions"]["capacity"] <= 100.0
    assert 0.0 <= pulse["dimensions"]["events"] <= 100.0
    assert 0.0 <= pulse["dimensions"]["environment"] <= 100.0

    assert 0.0 <= pulse["confidence"]["score"] <= 100.0
    assert 0.0 <= pulse["confidence"]["coverage"] <= 100.0

    assert pulse["trend"]["direction"] == "stable"
    assert pulse["trend"]["change"] == 0.0


def test_event_contributes_to_place_pulse() -> None:
    now = datetime.now(timezone.utc)
    event_start = (now - timedelta(hours=1)).isoformat()
    event_end = (now + timedelta(hours=1)).isoformat()

    destination_response = client.post(
        "/destinations",
        json={
            "country_code": "HU",
            "name": "Test Event Destination",
        },
    )

    assert destination_response.status_code == 201

    destination_id = destination_response.json()["id"]

    place_response = client.post(
        f"/destinations/{destination_id}/places",
        json={
            "name": "Budapest Event Test",
            "place_type": "destination",
        },
    )

    assert place_response.status_code == 201

    place_id = place_response.json()["id"]

    event_response = client.post(
        f"/places/{place_id}/events",
        json={
            "name": "Budapest Summer Festival",
            "event_type": "festival",
            "description": "Test event",
            "start_at": event_start,
            "end_at": event_end,
            "source_url": "https://example.com/event",
        },
    )

    assert event_response.status_code == 201

    response = client.get(
        f"/places/{place_id}/pulse",
    )

    assert response.status_code == 200

    pulse = response.json()

    assert pulse["dimensions"]["events"] > 0
    assert pulse["pulse"] > 0

def test_pulse_snapshot_is_persisted() -> None:
    destination_response = client.post(
        "/destinations",
        json={
            "country_code": "HU",
            "name": "Snapshot Test Destination",
        },
    )

    assert destination_response.status_code == 201

    destination_id = destination_response.json()["id"]

    place_response = client.post(
        f"/destinations/{destination_id}/places",
        json={
            "name": "Snapshot Test Place",
            "place_type": "destination",
        },
    )

    assert place_response.status_code == 201

    place_id = place_response.json()["id"]

    signal_response = client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "occupancy",
            "value": 80,
            "unit": "percent",
            "observed_at": "2026-08-20T10:00:00Z",
            "source": "government",
        },
    )

    assert signal_response.status_code == 201

    pulse_response = client.get(
        f"/places/{place_id}/pulse",
    )

    assert pulse_response.status_code == 200

    history_response = client.get(
        f"/places/{place_id}/pulse/history",
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 1
    assert history[0]["place_id"] == place_id
    assert history[0]["pulse"] == pulse_response.json()["pulse"]


def test_pulse_persist_false_does_not_write_a_snapshot() -> None:
    destination_response = client.post(
        "/destinations",
        json={
            "country_code": "HU",
            "name": "No Persist Test Destination",
        },
    )

    assert destination_response.status_code == 201

    destination_id = destination_response.json()["id"]

    place_response = client.post(
        f"/destinations/{destination_id}/places",
        json={
            "name": "No Persist Test Place",
            "place_type": "destination",
        },
    )

    assert place_response.status_code == 201

    place_id = place_response.json()["id"]

    signal_response = client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "occupancy",
            "value": 80,
            "unit": "percent",
            "observed_at": "2026-08-20T10:00:00Z",
            "source": "government",
        },
    )

    assert signal_response.status_code == 201

    for _ in range(3):
        pulse_response = client.get(
            f"/places/{place_id}/pulse",
            params={"persist": "false"},
        )
        assert pulse_response.status_code == 200

    history_response = client.get(f"/places/{place_id}/pulse/history")

    assert history_response.status_code == 200
    # Three persist=false calls must not have written any snapshots.
    assert history_response.json() == []

    # persist defaults to true and still works normally afterward.
    persisted_response = client.get(f"/places/{place_id}/pulse")
    assert persisted_response.status_code == 200

    history_after = client.get(f"/places/{place_id}/pulse/history").json()
    assert len(history_after) == 1


def test_pulse_trend_uses_previous_snapshot() -> None:
    destination_response = client.post(
        "/destinations",
        json={
            "country_code": "HU",
            "name": "Trend Test Destination",
        },
    )

    assert destination_response.status_code == 201

    destination_id = destination_response.json()["id"]

    place_response = client.post(
        f"/destinations/{destination_id}/places",
        json={
            "name": "Trend Test Place",
            "place_type": "destination",
        },
    )

    assert place_response.status_code == 201

    place_id = place_response.json()["id"]

    first_signal = client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "occupancy",
            "value": 40,
            "unit": "percent",
            "observed_at": "2026-08-20T10:00:00Z",
            "source": "government",
        },
    )

    assert first_signal.status_code == 201

    first_pulse = client.get(
        f"/places/{place_id}/pulse",
    )

    assert first_pulse.status_code == 200
    assert first_pulse.json()["trend"]["direction"] == "stable"
    assert first_pulse.json()["trend"]["change"] == 0.0

    second_signal = client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "occupancy",
            "value": 90,
            "unit": "percent",
            "observed_at": "2026-08-20T11:00:00Z",
            "source": "government",
        },
    )

    assert second_signal.status_code == 201

    second_pulse = client.get(
        f"/places/{place_id}/pulse",
    )

    assert second_pulse.status_code == 200

    trend = second_pulse.json()["trend"]

    assert trend["direction"] == "up"
    assert trend["change"] > 0
