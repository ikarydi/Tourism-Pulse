"""Create or update generated places for regions, areas and cities."""

import math
from dataclasses import dataclass, field

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Destination, NutsRegion, Place, RegionalIndicator
from tourism_pulse_api.ingestion.eu_locations.parser import EU27, CityPoint
from tourism_pulse_api.ingestion.eurostat.parser import eurostat_geo_code
from tourism_pulse_api.ingestion.ksh.parser import SUPPORTED_REGIONS

# A city this close to a curated destination in the same country is that
# destination: link its statistics instead of creating a duplicate.
SAME_PLACE_KM = 12.0

# KSH tourism areas: map point = the area's main town.
KSH_AREA_POINTS: dict[str, tuple[float, float]] = {
    "greater_budapest": (47.669, 19.075),  # Szentendre
    "buk_sarvar": (47.384, 16.750),  # Bük
    "gyor_pannonhalma": (47.687, 17.650),  # Győr
    "gyula": (46.646, 21.278),
    "eger": (47.902, 20.377),
    "pecs": (46.072, 18.232),
    "sopron": (47.685, 16.590),
    "szeged": (46.253, 20.141),
    "tokaj_nyiregyhaza": (47.955, 21.717),  # Nyíregyháza
}

_POINT_ON_SURFACE = text(
    "SELECT ST_Y(p), ST_X(p) FROM (SELECT ST_PointOnSurface(geom) AS p "
    "FROM nuts_regions WHERE code = :code) AS s"
)


@dataclass
class LocationSummary:
    regions: int = 0
    areas: int = 0
    cities_created: int = 0
    cities_linked: list[str] = field(default_factory=list)
    ksh_areas: int = 0
    skipped_no_country: set[str] = field(default_factory=set)


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    to_rad = math.radians
    dlat, dlon = to_rad(lat2 - lat1), to_rad(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _country_destinations(db: Session) -> dict[str, int]:
    """Eurostat country code -> the country place's destination id."""
    return {
        place.nuts_code: place.destination_id
        for place in db.query(Place).filter(Place.place_type == "country")
        if place.nuts_code
    }


def _upsert_place(db: Session, source_code: str, **fields) -> Place:
    place = db.query(Place).filter(Place.source_code == source_code).one_or_none()
    if place is None:
        place = Place(source_code=source_code, **fields)
        db.add(place)
    else:
        for key, value in fields.items():
            setattr(place, key, value)
    return place


def ensure_region_places(db: Session, summary: LocationSummary) -> None:
    """A place for every EU27 NUTS 2 / NUTS 3 region with indicators and a
    boundary in nuts_regions."""
    destinations = _country_destinations(db)
    with_data = {
        code
        for (code,) in db.query(RegionalIndicator.nuts_code).distinct()
        if len(code) in (4, 5) and code[:2] in EU27
    }
    regions = db.query(NutsRegion).filter(
        NutsRegion.code.in_(with_data), func.length(NutsRegion.code).in_([4, 5])
    )
    for region in regions:
        destination_id = destinations.get(region.country_code)
        if destination_id is None:
            summary.skipped_no_country.add(region.country_code)
            continue
        latitude, longitude = db.execute(_POINT_ON_SURFACE, {"code": region.code}).one()
        level_two = len(region.code) == 4
        _upsert_place(
            db,
            f"NUTS{2 if level_two else 3}:{region.code}",
            destination_id=destination_id,
            name=region.name,
            place_type="region" if level_two else "area",
            latitude=latitude,
            longitude=longitude,
            nuts_code=region.code if level_two else region.code[:4],
            nuts3_code=None if level_two else region.code,
        )
        if level_two:
            summary.regions += 1
        else:
            summary.areas += 1
    db.commit()


def ensure_city_places(
    db: Session, points: list[CityPoint], with_data: set[str], summary: LocationSummary
) -> None:
    destinations = _country_destinations(db)
    curated = [
        place
        for place in db.query(Place).filter(Place.place_type == "destination")
        if place.latitude is not None and place.longitude is not None
    ]
    for point in points:
        if point.code not in with_data:
            continue
        match = min(
            (
                (distance, place)
                for place in curated
                if place.destination
                and eurostat_geo_code(place.destination.country_code) == point.country_code
                and (
                    distance := _km(
                        point.latitude, point.longitude, place.latitude, place.longitude
                    )
                )
                <= SAME_PLACE_KM
            ),
            default=None,
            key=lambda item: item[0],
        )
        if match is not None:
            place = match[1]
            place.urau_code = point.code
            summary.cities_linked.append(f"{place.name} = {point.name}")
            continue
        destination_id = destinations.get(point.country_code)
        if destination_id is None:
            summary.skipped_no_country.add(point.country_code)
            continue
        _upsert_place(
            db,
            f"URAU:{point.code}",
            destination_id=destination_id,
            name=point.name,
            place_type="city",
            latitude=point.latitude,
            longitude=point.longitude,
            urau_code=point.code,
        )
        summary.cities_created += 1
    db.commit()


def ensure_ksh_area_places(db: Session, summary: LocationSummary) -> None:
    """Hungary's KSH tourism areas as curated places (the KSH adapter and
    scheduler find them by name)."""
    existing = {place.name for place in db.query(Place).filter(Place.place_type == "destination")}
    for key, (latitude, longitude) in KSH_AREA_POINTS.items():
        name = SUPPORTED_REGIONS[key].place_name
        if name in existing:
            continue
        destination = Destination(country_code="HU", name=name)
        db.add(destination)
        db.flush()
        db.add(
            Place(
                destination_id=destination.id,
                name=name,
                place_type="destination",
                latitude=latitude,
                longitude=longitude,
                source_code=f"KSH:{key}",
            )
        )
        summary.ksh_areas += 1
    db.commit()
