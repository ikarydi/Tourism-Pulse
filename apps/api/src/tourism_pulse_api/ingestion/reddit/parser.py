"""Contract for a subreddit listing (`/r/<name>/new`).

Reads `data.after` and, per child of kind t3, `created_utc`, `title` and
`selftext`. A missing field raises ValueError so a format change fails the
run (and the contract test) instead of producing wrong counts.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Post:
    created_at: datetime
    text: str


@dataclass(frozen=True)
class Listing:
    posts: list[Post]
    after: str | None


def parse_listing(text: str) -> Listing:
    try:
        payload = json.loads(text)
        data = payload["data"]
        posts = [
            Post(
                created_at=datetime.fromtimestamp(float(child["data"]["created_utc"]), tz=UTC),
                text=f"{child['data']['title']}\n{child['data'].get('selftext') or ''}",
            )
            for child in data["children"]
            if child["kind"] == "t3"
        ]
        after = data.get("after")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected Reddit listing: {exc}") from exc
    return Listing(posts=posts, after=after)
