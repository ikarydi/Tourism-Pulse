"""Reddit Data API: app-only OAuth and subreddit `new` listings.

Reddit asks every client for a descriptive User-Agent
("<platform>:<app id>:<version> (by /u/<username>)") and allows 100
requests a minute per OAuth client; one request a second keeps well under.
"""

import base64
import json
import time
import urllib.parse
import urllib.request

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"
PAGE_SIZE = 100
MAX_PAGES = 10  # Reddit's listings stop at about 1,000 items


def app_only_token(*, client_id: str, client_secret: str, user_agent: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": f"Basic {credentials}", "User-Agent": user_agent},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)["access_token"]


def listing_url(subreddit: str, after: str | None) -> str:
    params = {"limit": str(PAGE_SIZE), "raw_json": "1"}
    if after:
        params["after"] = after
    return f"{API_BASE}/r/{urllib.parse.quote(subreddit)}/new?{urllib.parse.urlencode(params)}"


def fetch_listing_pages(
    *, subreddit: str, token: str, user_agent: str, max_pages: int = MAX_PAGES
) -> list[str]:
    """Raw JSON text of each `new` page, newest first, until the listing
    ends or `max_pages` is reached."""
    from tourism_pulse_api.ingestion.reddit.parser import parse_listing

    pages: list[str] = []
    after: str | None = None
    for _ in range(max_pages):
        request = urllib.request.Request(
            listing_url(subreddit, after),
            headers={"Authorization": f"Bearer {token}", "User-Agent": user_agent},
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            text = response.read().decode("utf-8")
        pages.append(text)
        after = parse_listing(text).after
        if after is None:
            break
        time.sleep(1.0)
    return pages
