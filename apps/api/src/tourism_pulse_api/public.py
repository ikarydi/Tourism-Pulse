"""Public mode: what an unauthenticated internet visitor may reach.

The API has no login, and several endpoints write (create places,
signals, events, saved views) or spend money (the Groq-backed /explore/ask
and the pulse narrative). With PUBLIC_MODE=true the same app can be put
online as the free Pressure Index: reads stay open, everything else is
refused, and the paid Destination Pressure Brief is not served at all.

Off by default, so local development is unchanged.
"""

import re

from fastapi import Request
from fastapi.responses import JSONResponse

from tourism_pulse_api.settings import settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# POST endpoints that only read: the explore query builder takes its
# chart spec in the body.
READ_ONLY_POSTS = {"/explore/query"}

# Reads that are not public: saved views are the operator's own, and the
# brief is the paid product.
PRIVATE_PATHS = (
    re.compile(r"^/explore/views(/|$)"),
    re.compile(r"^/places/\d+/brief(\.html)?$"),
)


def allowed_in_public_mode(method: str, path: str) -> bool:
    path = path.rstrip("/") or "/"
    if any(pattern.match(path) for pattern in PRIVATE_PATHS):
        return False
    if method.upper() in SAFE_METHODS:
        return True
    return method.upper() == "POST" and path in READ_ONLY_POSTS


async def public_mode_guard(request: Request, call_next):
    if settings.public_mode and not allowed_in_public_mode(request.method, request.url.path):
        return JSONResponse(
            status_code=403,
            content={"detail": "Not available on the public Tourism Pulse API."},
        )
    return await call_next(request)
