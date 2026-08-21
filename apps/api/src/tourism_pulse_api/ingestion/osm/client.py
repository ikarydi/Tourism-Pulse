"""Network client for the OpenStreetMap Overpass API.

Free, no API key. The public instance's own usage policy warns that
commercial access can be withdrawn without notice - fine for building and
running this now, but a paid/dedicated Overpass instance (e.g. Geofabrik)
is the right move if this becomes a production-critical dependency.
https://operations.osmfoundation.org/policies/api/

Kept separate from parser.py so unit tests can exercise the parser against
fixtures without ever touching the network.
"""

import urllib.error
import urllib.parse
import urllib.request

from tourism_pulse_api.ingestion.osm.parser import CATEGORY_TAG_QUERIES

OVERPASS_BASE_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_TIMEOUT_SECONDS = 40.0
DEFAULT_RADIUS_METERS = 10_000


def build_overpass_query(
    *,
    category: str,
    latitude: float,
    longitude: float,
    radius_meters: int = DEFAULT_RADIUS_METERS,
) -> str:
    """Overpass QL query for every node/way tagged as `category` within a radius.

    `out center` makes the API attach a computed centroid to way/relation
    elements (which have no direct lat/lon of their own) alongside nodes'
    native coordinates - see parser._element_coordinates.
    """
    if category not in CATEGORY_TAG_QUERIES:
        raise ValueError(
            f"Unsupported category: {category!r}. "
            f"Expected one of: {sorted(CATEGORY_TAG_QUERIES)}"
        )

    tag_key, tag_value = CATEGORY_TAG_QUERIES[category]
    around = f"around:{radius_meters},{latitude},{longitude}"

    return (
        "[out:json][timeout:25];\n"
        "(\n"
        f'  node["{tag_key}"="{tag_value}"]({around});\n'
        f'  way["{tag_key}"="{tag_value}"]({around});\n'
        ");\n"
        "out center;"
    )


def fetch_pois(
    *,
    category: str,
    latitude: float,
    longitude: float,
    radius_meters: int = DEFAULT_RADIUS_METERS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    base_url: str = OVERPASS_BASE_URL,
) -> str:
    """Fetch raw Overpass JSON text for one category within a radius of a point.

    Raises `urllib.error.URLError` / `TimeoutError` on failure - callers
    decide how to surface that (Overpass can be slow or briefly overloaded;
    a generous timeout is used deliberately).
    """
    query = build_overpass_query(
        category=category,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        base_url,
        data=data,
        headers={"User-Agent": "tourism-pulse-ingestion/1.0"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read()

    return raw.decode("utf-8")
