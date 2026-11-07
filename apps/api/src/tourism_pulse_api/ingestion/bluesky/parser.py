"""Contract for `app.bsky.feed.searchPosts`: reads `cursor` and, per post,
`record.text` and `record.langs`. A missing field raises ValueError."""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchPage:
    texts: list[str]
    languages: list[str]
    cursor: str | None


def parse_search_page(text: str) -> SearchPage:
    try:
        payload = json.loads(text)
        records = [post["record"] for post in payload["posts"]]
        texts = [str(record["text"]) for record in records]
        languages = [
            (record.get("langs") or ["unknown"])[0].split("-")[0].lower() for record in records
        ]
        cursor = payload.get("cursor") or None
    except (json.JSONDecodeError, KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError(f"Unexpected Bluesky search response: {exc}") from exc
    return SearchPage(texts=texts, languages=languages, cursor=cursor)
