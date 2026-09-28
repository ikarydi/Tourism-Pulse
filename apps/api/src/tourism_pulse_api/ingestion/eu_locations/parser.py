"""Parsers for GISCO city label points and Eurostat city tourism data."""

import json
from dataclasses import dataclass

GISCO_SOURCE_NAME = "gisco"
URAU_POINTS_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/urau/geojson/"
    "URAU_LB_2021_4326_CITIES.geojson"
)
CITY_TOURISM_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_ctour"
    "?format=JSON&lang=EN&indic_ur=CR2001V&indic_ur=CR2009V&sinceTimePeriod=2015"
)

EU27 = frozenset(
    "AT BE BG CY CZ DE DK EE EL ES FI FR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split()
)


@dataclass(frozen=True)
class CityPoint:
    code: str
    name: str
    country_code: str  # Eurostat code (EL for Greece)
    latitude: float
    longitude: float


def parse_city_points(text: str) -> list[CityPoint]:
    payload = json.loads(text)
    points = []
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        country = properties.get("CNTR_CODE")
        if geometry.get("type") != "Point" or country not in EU27:
            continue
        longitude, latitude = geometry["coordinates"][:2]
        points.append(
            CityPoint(
                code=properties["URAU_CODE"],
                name=properties.get("URAU_NAME") or properties["URAU_CODE"],
                country_code=country,
                latitude=float(latitude),
                longitude=float(longitude),
            )
        )
    if not points:
        raise ValueError("GISCO city response has no EU27 city points")
    return points


def cities_with_tourism_data(payload: dict) -> set[str]:
    """Urban Audit city codes that have any tourism value in urb_ctour."""
    dimension = payload["dimension"]
    geo_key = "cities" if "cities" in dimension else "geo"
    ids, sizes = payload["id"], payload["size"]
    geo_position = ids.index(geo_key)
    by_index = {i: code for code, i in dimension[geo_key]["category"]["index"].items()}
    stride = 1
    for size in sizes[geo_position + 1 :]:
        stride *= size
    codes = set()
    for flat in payload.get("value", {}):
        code = by_index[(int(flat) // stride) % sizes[geo_position]]
        if len(code) > 2 and code[:2] in EU27:
            codes.add(code)
    return codes
