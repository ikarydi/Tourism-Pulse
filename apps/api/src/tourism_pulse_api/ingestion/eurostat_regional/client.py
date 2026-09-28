"""Network client for Eurostat's regional tourism datasets."""

import urllib.request

DEFAULT_TIMEOUT_SECONDS = 120.0


def fetch_dataset(url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "tourism-pulse-ingestion/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8")
