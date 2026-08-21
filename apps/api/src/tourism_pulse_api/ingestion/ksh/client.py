"""Network client for downloading the KSH STADAT 27.2.1.19 CSV export.

Kept separate from parser.py so unit tests can exercise the parser against a
fixture without ever touching the network.
"""

import urllib.request

from tourism_pulse_api.ingestion.ksh.parser import KSH_CSV_URL

DEFAULT_TIMEOUT_SECONDS = 30.0

# KSH serves this export in the ISO-8859-2 (Central European / "Latin-2")
# code page, which is what its accented Hungarian place names require.
KSH_ENCODING = "iso-8859-2"


def fetch_ksh_csv(
    url: str = KSH_CSV_URL,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Download the KSH CSV export and decode it to text.

    Raises whatever `urllib.error.URLError` / `TimeoutError` the underlying
    request raises on failure - callers decide how to surface that.
    """
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode(KSH_ENCODING)
