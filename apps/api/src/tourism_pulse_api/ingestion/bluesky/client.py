"""AT Protocol calls: create a session, search posts in a time window."""

import json
import time
import urllib.parse
import urllib.request

SERVICE = "https://bsky.social"
SESSION_URL = f"{SERVICE}/xrpc/com.atproto.server.createSession"
SEARCH_URL = f"{SERVICE}/xrpc/app.bsky.feed.searchPosts"
PAGE_SIZE = 100
USER_AGENT = "TourismPulse/1.0 (https://github.com/ikarydi/Tourism-Pulse)"


def create_session(*, handle: str, app_password: str) -> str:
    request = urllib.request.Request(
        SESSION_URL,
        data=json.dumps({"identifier": handle, "password": app_password}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)["accessJwt"]


def search_url(*, query: str, since: str, until: str, cursor: str | None) -> str:
    params = {
        "q": query,
        "sort": "latest",
        "since": since,
        "until": until,
        "limit": str(PAGE_SIZE),
    }
    if cursor:
        params["cursor"] = cursor
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def search_page(*, token: str, query: str, since: str, until: str, cursor: str | None) -> str:
    request = urllib.request.Request(
        search_url(query=query, since=since, until=until, cursor=cursor),
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        text = response.read().decode("utf-8")
    time.sleep(0.5)
    return text
