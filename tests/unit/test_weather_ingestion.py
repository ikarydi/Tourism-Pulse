from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tourism_pulse_api.db.models import Destination, Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.weather.parser import WeatherObservation
from tourism_pulse_api.ingestion.weather.service import (
    WEATHER_COMFORT_SIGNAL_TYPE,
    build_preview,
    upsert_weather_signals,
)


def make_observation(
    *,
    observed_at: datetime = datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
    temperature_c: float = 22.0,
    humidity_percent: float = 50,
    precipitation_mm: float = 0.0,
    wind_speed_kmh: float = 8.0,
    weather_code: int = 1,
) -> WeatherObservation:
    return WeatherObservation(
        observed_at=observed_at,
        latitude=47.4979,
        longitude=19.0402,
        temperature_c=Decimal(str(temperature_c)),
        humidity_percent=Decimal(str(humidity_percent)),
        precipitation_mm=Decimal(str(precipitation_mm)),
        wind_speed_kmh=Decimal(str(wind_speed_kmh)),
        weather_code=weather_code,
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
    destination = Destination(country_code="HU", name="Weather Test Destination")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    place = Place(
        destination_id=destination.id,
        name="Weather Test Place",
        place_type="destination",
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)

    return place


def test_build_preview_keeps_raw_and_comfort_separate() -> None:
    observation = make_observation(temperature_c=30.5, precipitation_mm=0.0, wind_speed_kmh=10.1)

    preview = build_preview(observation)

    assert preview.comfort_score != float(observation.temperature_c)
    assert "30.5" in preview.raw_readings["temperature"]
    assert preview.target_dimension == "environment"
    assert 0.0 <= preview.comfort_score <= 100.0


def test_upsert_creates_five_signals_with_raw_metadata(db_session, test_place) -> None:
    observation = make_observation()

    results = upsert_weather_signals(
        db_session,
        place_id=test_place.id,
        observation=observation,
        source_url="https://api.open-meteo.com/v1/forecast?...",
    )

    signal_types = {signal.signal_type for signal, _ in results}
    assert signal_types == {
        "temperature",
        "humidity",
        "precipitation",
        "wind_speed",
        WEATHER_COMFORT_SIGNAL_TYPE,
    }
    assert all(created for _, created in results)
    assert all(signal.source == "open-meteo" for signal, _ in results)
    assert all(signal.place_id == test_place.id for signal, _ in results)
    assert all(signal.observed_at == observation.observed_at for signal, _ in results)

    temperature_signal = next(s for s, _ in results if s.signal_type == "temperature")
    assert temperature_signal.value == Decimal("22.0")
    assert temperature_signal.unit == "celsius"

    comfort_signal = next(s for s, _ in results if s.signal_type == WEATHER_COMFORT_SIGNAL_TYPE)
    assert comfort_signal.unit == "percent"
    assert 0 <= comfort_signal.value <= 100


def test_upsert_is_idempotent_within_the_same_reading(db_session, test_place) -> None:
    observation = make_observation()

    first = upsert_weather_signals(
        db_session, place_id=test_place.id, observation=observation, source_url="https://a"
    )
    second = upsert_weather_signals(
        db_session, place_id=test_place.id, observation=observation, source_url="https://b"
    )

    assert all(created for _, created in first)
    assert all(not created for _, created in second)
    assert {s.id for s, _ in first} == {s.id for s, _ in second}

    count = (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.source == "open-meteo")
        .count()
    )
    assert count == 5


def test_new_reading_time_creates_fresh_rows_not_an_update(db_session, test_place) -> None:
    first_observation = make_observation(observed_at=datetime(2026, 8, 21, 10, 0, tzinfo=UTC))
    second_observation = make_observation(observed_at=datetime(2026, 8, 21, 10, 15, tzinfo=UTC))

    upsert_weather_signals(
        db_session, place_id=test_place.id, observation=first_observation, source_url="https://a"
    )
    upsert_weather_signals(
        db_session, place_id=test_place.id, observation=second_observation, source_url="https://a"
    )

    count = (
        db_session.query(Signal)
        .filter(Signal.place_id == test_place.id, Signal.source == "open-meteo")
        .count()
    )
    assert count == 10
