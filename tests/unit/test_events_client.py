from datetime import UTC, datetime

from tourism_pulse_api.ingestion.events.client import build_public_source_url, build_request_url


def test_build_request_url_includes_the_real_api_key() -> None:
    url = build_request_url(api_key="super-secret-key", city="Budapest", country_code="HU")

    assert "apikey=super-secret-key" in url


def test_build_request_url_includes_city_and_country() -> None:
    url = build_request_url(api_key="k", city="Budapest", country_code="HU")

    assert "city=Budapest" in url
    assert "countryCode=HU" in url


def test_build_request_url_includes_start_date_time_in_required_format() -> None:
    url = build_request_url(
        api_key="k",
        city="Budapest",
        country_code="HU",
        start_date_time=datetime(2026, 8, 21, 10, 30, tzinfo=UTC),
    )

    assert "startDateTime=2026-08-21T10%3A30%3A00Z" in url


def test_public_source_url_never_contains_the_real_api_key() -> None:
    url = build_public_source_url(city="Budapest", country_code="HU")

    assert "super-secret" not in url
    assert "apikey=REDACTED" in url


def test_public_source_url_still_carries_the_search_parameters() -> None:
    url = build_public_source_url(city="Budapest", country_code="HU")

    assert "city=Budapest" in url
    assert "countryCode=HU" in url
