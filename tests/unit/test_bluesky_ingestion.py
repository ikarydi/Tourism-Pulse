import json
import urllib.parse
from pathlib import Path

import pytest
from tourism_pulse_api.ingestion.bluesky.client import search_url
from tourism_pulse_api.ingestion.bluesky.parser import parse_search_page
from tourism_pulse_api.ingestion.bluesky.service import month_result

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bluesky_search_budapest_sample.json"


def test_contract_reads_text_language_and_cursor() -> None:
    page = parse_search_page(FIXTURE.read_text(encoding="utf-8"))
    assert page.cursor == "100"
    assert page.texts[0] == "Budapest Christmas market is so crowded tonight"
    assert page.languages == ["en", "hu", "unknown"]


@pytest.mark.parametrize("text", ["nope", "{}", '{"posts": [{"uri": "x"}]}'])
def test_contract_rejects_unexpected_shapes(text: str) -> None:
    with pytest.raises(ValueError):
        parse_search_page(text)


def test_search_is_bounded_to_the_month() -> None:
    url = search_url(
        query="Budapest", since="2026-10-01T00:00:00Z", until="2026-11-01T00:00:00Z", cursor=None
    )
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert params == {
        "q": "Budapest",
        "sort": "latest",
        "since": "2026-10-01T00:00:00Z",
        "until": "2026-11-01T00:00:00Z",
        "limit": "100",
    }


def _page(texts: list[str], cursor: str | None) -> str:
    return json.dumps(
        {"cursor": cursor, "posts": [{"record": {"text": t, "langs": ["en"]}} for t in texts]}
    )


def test_month_is_paged_to_the_end() -> None:
    pages = {None: _page(["crowded", "nice"], "2"), "2": _page(["queue again"], None)}
    result = month_result(lambda cursor: pages[cursor])
    assert result is not None
    assert result.posts == 3
    assert result.felt_pressure_share == pytest.approx(2 / 3)
    assert result.languages == {"en": 3}


def test_month_over_the_page_cap_is_not_stored() -> None:
    assert month_result(lambda cursor: _page(["x"], "more"), max_pages=3) is None
