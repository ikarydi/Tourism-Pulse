from tourism_pulse_api.ingestion.gdacs.client import build_request_url


def test_build_request_url_includes_country() -> None:
    url = build_request_url(country="HU")

    assert "country=HU" in url


def test_build_request_url_uses_search_endpoint() -> None:
    url = build_request_url(country="HU")

    assert url.startswith("https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH")
