"""Contract for the one field this adapter reads from `search.list`."""

import json

# YouTube caps its estimate here; a month at the cap is not a count.
TOTAL_RESULTS_CAP = 1_000_000


def parse_total_results(text: str) -> int:
    """`pageInfo.totalResults` as an int. Raises ValueError when the answer
    is not the expected shape, so a format change fails loudly."""
    try:
        payload = json.loads(text)
        total = int(payload["pageInfo"]["totalResults"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected YouTube search response: {exc}") from exc
    if total < 0:
        raise ValueError(f"YouTube reported a negative totalResults: {total}")
    return total
