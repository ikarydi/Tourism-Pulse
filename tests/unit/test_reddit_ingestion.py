from datetime import UTC, datetime
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.reddit.client import listing_url
from tourism_pulse_api.ingestion.reddit.parser import Post, parse_listing
from tourism_pulse_api.ingestion.reddit.service import monthly_aggregates

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "reddit_listing_crete_sample.json"
NOW = datetime(2025, 11, 7, tzinfo=UTC)


def test_contract_reads_posts_and_next_page() -> None:
    listing = parse_listing(FIXTURE.read_text(encoding="utf-8"))
    assert listing.after == "t3_page2"
    assert len(listing.posts) == 4
    assert listing.posts[0].created_at == datetime(2025, 11, 2, tzinfo=UTC)
    assert listing.posts[2].text == "Rents in Heraklion\nEvery flat on my street is an Airbnb now."
    assert listing.posts[3].text == "Ferry from Piraeus\n"  # null selftext


def test_contract_keeps_no_author() -> None:
    listing = parse_listing(FIXTURE.read_text(encoding="utf-8"))
    assert "fixture_user" not in repr(listing)


@pytest.mark.parametrize(
    "text", ["nope", "{}", '{"data": {"children": [{"kind": "t3", "data": {}}]}}']
)
def test_contract_rejects_unexpected_shapes(text: str) -> None:
    with pytest.raises(ValueError):
        parse_listing(text)


def test_listing_url_pages_with_after() -> None:
    assert listing_url("crete", "t3_x").endswith("/r/crete/new?limit=100&raw_json=1&after=t3_x")


def _post(day: str, text: str = "hello") -> Post:
    return Post(datetime.fromisoformat(day).replace(tzinfo=UTC), text)


def test_month_is_kept_only_when_fully_covered() -> None:
    posts = [_post("2025-10-28", "so crowded"), _post("2025-10-02"), _post("2025-09-15")]
    aggregates = monthly_aggregates(posts, reached_end=False, now=NOW)
    # October: posts reach back into September, so October is complete.
    # September: the window starts mid-month, so it is not stored.
    assert [(a.month, a.posts, a.felt_pressure_share) for a in aggregates] == [("2025-10", 2, 0.5)]


def test_all_months_kept_when_the_listing_ended() -> None:
    posts = [_post("2025-10-28"), _post("2025-09-15")]
    assert [a.month for a in monthly_aggregates(posts, reached_end=True, now=NOW)] == [
        "2025-09",
        "2025-10",
    ]


def test_current_month_is_never_stored() -> None:
    posts = [_post("2025-11-02"), _post("2025-09-01")]
    assert "2025-11" not in [a.month for a in monthly_aggregates(posts, reached_end=True, now=NOW)]
