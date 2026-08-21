"""Network client for the OpenSky Network REST API.

Kept separate from parser.py so unit tests can exercise the parser
against a fixture response without ever touching the network.

Unlike every other adapter's single API key, OpenSky uses OAuth2
client-credentials: exchange a client_id/client_secret for a short-lived
bearer token, then call /states/all with it. Authentication is optional -
anonymous requests still work, just at a lower rate limit and coarser
time resolution (OpenSky's own documentation) - so `fetch_states` works
with no token at all, and `fetch_access_token` is only needed for
higher-quota access.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.opensky.parser import OPENSKY_STATES_URL

OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)

DEFAULT_TIMEOUT_SECONDS = 15.0


class TokenRequestError(RuntimeError):
    """Raised when exchanging client credentials for an access token
    fails - a wrong/expired client_id or client_secret, most likely."""


def fetch_access_token(
    *,
    client_id: str,
    client_secret: str,
    token_url: str = OPENSKY_TOKEN_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Exchange OAuth2 client credentials for a bearer access token.

    Raises `TokenRequestError` on a non-2xx response or an unexpected
    response shape; whatever `urllib.error.URLError` / `TimeoutError`
    the underlying request itself raises propagates to the caller.
    """
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        token_url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "tourism-pulse-ingestion/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise TokenRequestError(
            f"OpenSky token request failed with HTTP {exc.code}"
        ) from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
        return str(payload["access_token"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise TokenRequestError(f"Unexpected OpenSky token response shape: {exc}") from exc


def fetch_states(
    *,
    lamin: float,
    lomin: float,
    lamax: float,
    lomax: float,
    access_token: str | None = None,
    base_url: str = OPENSKY_STATES_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Fetch state vectors within a bounding box and return the raw JSON
    text. Works with `access_token=None` (anonymous, lower rate limit).

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    params = {
        "lamin": str(lamin),
        "lomin": str(lomin),
        "lamax": str(lamax),
        "lomax": str(lomax),
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    headers = {"User-Agent": "tourism-pulse-ingestion/1.0"}
    if access_token is not None:
        headers["Authorization"] = f"Bearer {access_token}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")
