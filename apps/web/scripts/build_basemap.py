"""Build the map's keyless basemap: European land outlines as GeoJSON.

Source: Natural Earth 1:50m admin-0 countries (public domain - no key,
no licence terms, no attribution required). Clipped to a European
extent, properties stripped, coordinates rounded to 2 decimals (~1 km,
plenty for the map's zoom range), written to public/basemap/.

    python scripts/build_basemap.py   (from apps/web)
"""

import json
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_50m_admin_0_countries.geojson"
)
OUTPUT = Path(__file__).resolve().parents[1] / "public" / "basemap" / "europe-land.geojson"
# lon_min, lat_min, lon_max, lat_max - Europe plus the Mediterranean rim.
EXTENT = (-32.0, 24.0, 60.0, 72.0)


def _points(geometry: dict):
    polygons = (
        geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    )
    for polygon in polygons:
        for ring in polygon:
            yield from ring


def _intersects_extent(geometry: dict) -> bool:
    lon_min, lat_min, lon_max, lat_max = EXTENT
    return any(
        lon_min <= lon <= lon_max and lat_min <= lat <= lat_max for lon, lat in _points(geometry)
    )


def _round(value):
    if isinstance(value, list):
        return [_round(item) for item in value]
    return round(value, 2)


def main() -> None:
    request = urllib.request.Request(
        SOURCE_URL, headers={"User-Agent": "tourism-pulse-basemap/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        source = json.load(response)

    features = [
        {
            "type": "Feature",
            "properties": {"name": feature["properties"].get("NAME", "")},
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": _round(feature["geometry"]["coordinates"]),
            },
        }
        for feature in source["features"]
        if feature.get("geometry") and _intersects_extent(feature["geometry"])
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
    )
    print(f"{OUTPUT.name}: {len(features)} countries, {OUTPUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
