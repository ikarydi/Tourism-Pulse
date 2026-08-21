"""Parser for OpenStreetMap Overpass API responses.

https://wiki.openstreetmap.org/wiki/Overpass_API

Unlike the government-statistics sources (KSH, Eurostat), OSM is a live,
crowd-edited map, not a published series - there is no "period" a POI
observation belongs to, only "what the map says right now". Each ingestion
run is a fresh snapshot: `category="hotel"` (`tourism=hotel`) or
`category="restaurant"` (`amenity=restaurant`), queried within a radius of
a place's coordinates via Overpass QL's `around` filter.

Elements come back as `node` (a point - has `lat`/`lon` directly) or `way`
(an area, e.g. a large hotel building - has no direct coordinate, only
member node references) or occasionally `relation`. Querying with
`out center;` makes the API compute and attach a `center` point to
way/relation elements, so every element type ends up with a usable
coordinate one way or another (see `_element_coordinates`).

OSM tag data is entirely user-contributed and inconsistent: `name` is
occasionally missing (dropped rather than invented), most other tags are
optional. Data is ODbL-licensed - anything derived from it and displayed
must credit OpenStreetMap contributors (see the frontend attribution).
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

OSM_SOURCE_NAME = "osm"

HOTEL_CATEGORY = "hotel"
RESTAURANT_CATEGORY = "restaurant"

# Overpass tag -> our category vocabulary (matches the master spec's
# attraction/hotel/restaurant entity naming).
CATEGORY_TAG_QUERIES: dict[str, tuple[str, str]] = {
    HOTEL_CATEGORY: ("tourism", "hotel"),
    RESTAURANT_CATEGORY: ("amenity", "restaurant"),
}


@dataclass(frozen=True)
class OsmPoi:
    """One point of interest parsed from an Overpass response."""

    osm_type: str  # "node" | "way" | "relation"
    osm_id: int
    category: str  # "hotel" | "restaurant"
    name: str
    latitude: float | None
    longitude: float | None
    description: str | None

    @property
    def external_id(self) -> str:
        """Stable identifier for idempotent upsert: unique per OSM element."""
        return f"{self.osm_type}/{self.osm_id}"


def _element_coordinates(element: dict) -> tuple[float | None, float | None]:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])

    center = element.get("center")

    if center and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])

    return None, None


def _describe(tags: dict, *, category: str) -> str | None:
    """Build a short human-readable description from whatever tags exist."""
    if category == HOTEL_CATEGORY:
        stars = tags.get("stars")
        parts = [f"{stars}-star hotel" if stars else "Hotel"]
    else:
        cuisine = tags.get("cuisine")
        parts = [f"{cuisine.replace('_', ' ').title()} restaurant" if cuisine else "Restaurant"]

    address_bits = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
    ]
    address = " ".join(bit for bit in address_bits if bit)

    if address:
        parts.append(f"at {address}")

    return " ".join(parts) if parts else None


def parse_overpass_pois(text: str, *, category: str) -> list[OsmPoi]:
    """Parse an Overpass JSON response into POIs of the given category.

    Elements with no name are skipped - OSM's `name` tag is frequently
    absent for smaller venues, and a nameless row is not useful to show a
    user or count meaningfully differently from "not mapped at all".
    Raises `ValueError` for a non-JSON or error response.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Overpass response is not valid JSON: {exc}") from exc

    if "remark" in payload and "elements" not in payload:
        raise ValueError(f"Overpass API error: {payload['remark']}")

    pois: list[OsmPoi] = []

    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name")

        if not name:
            continue

        latitude, longitude = _element_coordinates(element)

        pois.append(
            OsmPoi(
                osm_type=element["type"],
                osm_id=element["id"],
                category=category,
                name=name,
                latitude=latitude,
                longitude=longitude,
                description=_describe(tags, category=category),
            )
        )

    return pois


def parse_overpass_timestamp(text: str) -> datetime | None:
    """The underlying OSM data snapshot's timestamp, used as `observed_at`.

    Overpass reports this via `osm3s.timestamp_osm_base` on every response -
    it's the freshness of the map data itself, not the time we happened to
    query it, which is the more meaningful "as of" timestamp for a signal
    derived from it. Returns None if absent/unparseable rather than
    inventing a time (e.g. a hand-built test fixture that omits it).
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    raw = payload.get("osm3s", {}).get("timestamp_osm_base")

    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
