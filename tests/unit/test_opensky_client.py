import json
from urllib.error import HTTPError

import pytest
from tourism_pulse_api.ingestion.opensky.client import (
    TokenRequestError,
    fetch_access_token,
)


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_fetch_access_token_returns_token(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"access_token": "fake-token-123", "expires_in": 1800}).encode("utf-8")

    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        return _FakeResponse(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    token = fetch_access_token(client_id="id", client_secret="secret")

    assert token == "fake-token-123"


def test_fetch_access_token_raises_on_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"not json"

    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        return _FakeResponse(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(TokenRequestError):
        fetch_access_token(client_id="id", client_secret="secret")


def test_fetch_access_token_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        raise HTTPError(
            url="https://auth.example", code=401, msg="Unauthorized", hdrs=None, fp=None
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(TokenRequestError):
        fetch_access_token(client_id="id", client_secret="wrong-secret")
