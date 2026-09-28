"""Parser for GISCO NUTS GeoJSON (NUTS_RG_<scale>_<version>_4326_LEVL_<n>)."""

import json
from dataclasses import dataclass

GISCO_SOURCE_NAME = "gisco"
GISCO_BASE_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson"

# NUTS 2024 matches the codes of Eurostat's recent regional tourism data
# (e.g. Portugal's PT1A Grande Lisboa, which NUTS 2021 lacks).
DEFAULT_VERSION = "2024"
# 1:1 million. Coarser scales cut coastlines enough to put harbour towns
# (Valletta, Mykonos) outside every polygon.
DEFAULT_SCALE = "01M"


def build_geojson_url(*, level: int, version: str, scale: str) -> str:
    return f"{GISCO_BASE_URL}/NUTS_RG_{scale}_{version}_4326_LEVL_{level}.geojson"


@dataclass(frozen=True)
class NutsFeature:
    code: str
    level: int
    country_code: str
    name: str
    nuts_version: str
    geometry_json: str


def parse_nuts_geojson(text: str, *, version: str) -> list[NutsFeature]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GISCO response is not valid JSON: {exc}") from exc

    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("GISCO response has no features")

    parsed = []
    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry")
        if geometry is None or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        parsed.append(
            NutsFeature(
                code=properties["NUTS_ID"],
                level=int(properties["LEVL_CODE"]),
                country_code=properties["CNTR_CODE"],
                name=properties.get("NAME_LATN") or properties.get("NUTS_NAME") or "",
                nuts_version=version,
                geometry_json=json.dumps(geometry),
            )
        )

    if not parsed:
        raise ValueError("GISCO response has no polygon features")
    return parsed
