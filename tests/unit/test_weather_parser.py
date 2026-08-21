from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.weather.parser import (
    OPEN_METEO_SOURCE_NAME,
    build_request_url,
    parse_open_meteo_current,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "open_meteo_current_sample.json"
)


@pytest.fixture()
def sample_response_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parses_the_current_reading(sample_response_text: str) -> None:
    observation = parse_open_meteo_current(sample_response_text)

    assert observation.temperature_c == Decimal("30.5")
    assert observation.humidity_percent == Decimal("45")
    assert observation.precipitation_mm == 0
    assert observation.wind_speed_kmh == Decimal("10.1")
    assert observation.weather_code == 0


def test_observed_at_is_parsed_as_utc(sample_response_text: str) -> None:
    observation = parse_open_meteo_current(sample_response_text)

    assert observation.observed_at == datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


def test_coordinates_come_from_the_response(sample_response_text: str) -> None:
    observation = parse_open_meteo_current(sample_response_text)

    assert observation.latitude == pytest.approx(47.501236)
    assert observation.longitude == pytest.approx(19.03534)


def test_weather_description_from_wmo_code(sample_response_text: str) -> None:
    observation = parse_open_meteo_current(sample_response_text)

    assert observation.weather_description == "Clear sky"


def test_unknown_wmo_code_has_a_fallback_description() -> None:
    text = (
        '{"latitude":1.0,"longitude":1.0,"current":{"time":"2026-01-01T00:00",'
        '"temperature_2m":10,"relative_humidity_2m":50,"precipitation":0,'
        '"wind_speed_10m":5,"weather_code":999}}'
    )

    observation = parse_open_meteo_current(text)

    assert observation.weather_description == "Unknown conditions"


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_open_meteo_current("not json")


def test_missing_current_field_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_open_meteo_current('{"latitude": 1.0, "longitude": 1.0}')


def test_missing_reading_raises_value_error() -> None:
    text = (
        '{"latitude":1.0,"longitude":1.0,"current":{"time":"2026-01-01T00:00",'
        '"temperature_2m":10}}'
    )

    with pytest.raises(ValueError):
        parse_open_meteo_current(text)


def test_build_request_url_includes_coordinates_and_no_api_key() -> None:
    url = build_request_url(latitude=47.4979, longitude=19.0402)

    assert "latitude=47.4979" in url
    assert "longitude=19.0402" in url
    assert "key" not in url.lower()


def test_source_name_constant() -> None:
    assert OPEN_METEO_SOURCE_NAME == "open-meteo"
