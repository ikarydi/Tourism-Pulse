from datetime import date

from tourism_pulse_api.ingestion.wikipedia.client import build_request_url


def test_build_request_url_includes_article_and_project() -> None:
    url = build_request_url(
        article="Budapest",
        project="en.wikipedia.org",
        end_date=date(2026, 8, 20),
        days=30,
    )

    assert "en.wikipedia.org" in url
    assert "/Budapest/" in url


def test_build_request_url_replaces_spaces_with_underscores() -> None:
    url = build_request_url(
        article="New York City",
        end_date=date(2026, 8, 20),
    )

    assert "New_York_City" in url
    assert "New York City" not in url


def test_build_request_url_uses_default_agent() -> None:
    url = build_request_url(article="Budapest", end_date=date(2026, 8, 20))

    assert "/user/" in url


def test_build_request_url_respects_agent_override() -> None:
    url = build_request_url(
        article="Budapest",
        agent="all-agents",
        end_date=date(2026, 8, 20),
    )

    assert "/all-agents/" in url


def test_build_request_url_window_spans_requested_days() -> None:
    url = build_request_url(
        article="Budapest",
        days=30,
        end_date=date(2026, 8, 20),
    )

    assert "/daily/20260722/20260820" in url


def test_build_request_url_defaults_end_date_with_processing_lag() -> None:
    # No explicit end_date - just confirm it doesn't crash and produces a
    # well-formed daily/<start>/<end> suffix using "today".
    url = build_request_url(article="Budapest", days=1)

    assert "/daily/" in url
