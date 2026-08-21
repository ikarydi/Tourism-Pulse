from tourism_pulse_api.ingestion.youtube.client import (
    build_public_search_source_url,
    build_search_request_url,
)


def test_build_search_request_url_includes_the_real_api_key() -> None:
    url = build_search_request_url(api_key="super-secret-key", query="Budapest travel guide")

    assert "key=super-secret-key" in url


def test_build_search_request_url_includes_query_and_defaults() -> None:
    url = build_search_request_url(api_key="k", query="Budapest travel guide")

    assert "q=Budapest+travel+guide" in url
    assert "type=video" in url
    assert "part=snippet" in url


def test_build_search_request_url_includes_region_code_when_given() -> None:
    url = build_search_request_url(api_key="k", query="Budapest", region_code="HU")

    assert "regionCode=HU" in url


def test_build_search_request_url_omits_region_code_by_default() -> None:
    url = build_search_request_url(api_key="k", query="Budapest")

    assert "regionCode" not in url


def test_public_search_source_url_never_contains_the_real_api_key() -> None:
    url = build_public_search_source_url(query="Budapest travel guide")

    assert "super-secret" not in url
    assert "key=REDACTED" in url


def test_public_search_source_url_still_carries_the_query() -> None:
    url = build_public_search_source_url(query="Budapest travel guide")

    assert "q=Budapest+travel+guide" in url
