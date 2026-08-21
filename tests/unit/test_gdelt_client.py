from tourism_pulse_api.ingestion.gdelt.client import (
    build_artlist_url,
    build_timelinetone_url,
)


def test_build_artlist_url_includes_query_and_mode() -> None:
    url = build_artlist_url(query="Budapest tourism")

    assert "query=Budapest+tourism" in url
    assert "mode=artlist" in url
    assert "format=json" in url


def test_build_artlist_url_includes_timespan_and_max_records() -> None:
    url = build_artlist_url(query="Budapest tourism", timespan="1d", max_records=100)

    assert "timespan=1d" in url
    assert "maxrecords=100" in url


def test_build_artlist_url_has_no_api_key() -> None:
    # GDELT is fully open - there is nothing to redact.
    url = build_artlist_url(query="Budapest tourism")

    assert "key" not in url.lower()
    assert "apikey" not in url.lower()


def test_build_timelinetone_url_includes_query_and_mode() -> None:
    url = build_timelinetone_url(query="Budapest tourism")

    assert "query=Budapest+tourism" in url
    assert "mode=timelinetone" in url
    assert "format=json" in url
