"""A signal_type with no registered normalizer (raw-only/archival, e.g. the
raw weather readings a comfort score is derived from) must not crash Pulse
calculation - it should simply not contribute to any dimension, while
staying stored and queryable.
"""

from fastapi.testclient import TestClient
from tourism_pulse_api.main import app

client = TestClient(app)


def _create_place() -> int:
    destination_response = client.post(
        "/destinations",
        json={"country_code": "HU", "name": "Raw Signal Test Destination"},
    )
    assert destination_response.status_code == 201
    destination_id = destination_response.json()["id"]

    place_response = client.post(
        f"/destinations/{destination_id}/places",
        json={"name": "Raw Signal Test Place", "place_type": "destination"},
    )
    assert place_response.status_code == 201
    return place_response.json()["id"]


def test_raw_only_signal_type_does_not_crash_pulse_calculation() -> None:
    place_id = _create_place()

    # "temperature" has no entry in SIGNAL_NORMALIZERS - it is a raw,
    # archival-only reading (see ingestion.weather.service).
    response = client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "temperature",
            "value": 22.5,
            "unit": "celsius",
            "observed_at": "2026-08-21T10:00:00Z",
            "source": "open-meteo",
        },
    )
    assert response.status_code == 201

    # A raw-only signal alone still means "no supported signals" for Pulse
    # purposes, matching the existing 422 for a place with nothing usable.
    pulse_response = client.get(f"/places/{place_id}/pulse")
    assert pulse_response.status_code == 422


def test_raw_only_signal_is_ignored_but_a_real_one_still_contributes() -> None:
    place_id = _create_place()

    client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "temperature",
            "value": 22.5,
            "unit": "celsius",
            "observed_at": "2026-08-21T10:00:00Z",
            "source": "open-meteo",
        },
    )
    client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "weather_comfort",
            "value": 68.4,
            "unit": "percent",
            "observed_at": "2026-08-21T10:00:00Z",
            "source": "open-meteo",
        },
    )

    response = client.get(f"/places/{place_id}/pulse")

    assert response.status_code == 200
    pulse = response.json()
    assert pulse["dimensions"]["environment"] > 0


def test_raw_signal_remains_queryable_even_though_it_does_not_feed_pulse() -> None:
    place_id = _create_place()

    client.post(
        f"/places/{place_id}/signals",
        json={
            "signal_type": "temperature",
            "value": 22.5,
            "unit": "celsius",
            "observed_at": "2026-08-21T10:00:00Z",
            "source": "open-meteo",
        },
    )

    response = client.get(f"/places/{place_id}/signals")

    assert response.status_code == 200
    signals = response.json()
    assert any(s["signal_type"] == "temperature" for s in signals)
