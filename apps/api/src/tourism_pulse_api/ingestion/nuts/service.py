"""Load NUTS boundaries into PostGIS and assign places their NUTS code."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.ingestion.eurostat.parser import eurostat_geo_code
from tourism_pulse_api.ingestion.nuts.parser import NutsFeature

# A destination point just outside every polygon (a harbour, a beach) is
# given the nearest region if one lies within this distance.
NEAREST_REGION_MAX_METERS = 10_000

_UPSERT_REGION = text(
    """
    INSERT INTO nuts_regions (code, level, country_code, name, nuts_version, geom)
    VALUES (
        :code, :level, :country_code, :name, :nuts_version,
        ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometry_json), 4326))
    )
    ON CONFLICT (code) DO UPDATE SET
        level = EXCLUDED.level,
        country_code = EXCLUDED.country_code,
        name = EXCLUDED.name,
        nuts_version = EXCLUDED.nuts_version,
        geom = EXCLUDED.geom
    """
)

_REGION_FOR_POINT = text(
    """
    SELECT code
    FROM nuts_regions
    WHERE level = :level
      AND ST_DWithin(
          geom::geography,
          ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
          :max_meters
      )
    ORDER BY
        ST_Contains(geom, ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)) DESC,
        geom::geography <-> ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
    LIMIT 1
    """
)


def upsert_regions(db: Session, features: list[NutsFeature]) -> int:
    for feature in features:
        db.execute(
            _UPSERT_REGION,
            {
                "code": feature.code,
                "level": feature.level,
                "country_code": feature.country_code,
                "name": feature.name,
                "nuts_version": feature.nuts_version,
                "geometry_json": feature.geometry_json,
            },
        )
    db.commit()
    return len(features)


@dataclass(frozen=True)
class AssignmentResult:
    destinations_assigned: int
    destinations_unmatched: list[str]
    countries_assigned: int


def assign_place_nuts_codes(db: Session, *, level: int = 2) -> AssignmentResult:
    """Point-in-polygon for destinations, national code for countries."""
    assigned = 0
    unmatched: list[str] = []
    countries = 0

    for place in db.query(Place).all():
        if place.place_type == "country":
            country_code = place.destination.country_code if place.destination else None
            if country_code:
                place.nuts_code = eurostat_geo_code(country_code)
                countries += 1
            continue

        if place.latitude is None or place.longitude is None:
            continue

        code = db.execute(
            _REGION_FOR_POINT,
            {
                "level": level,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "max_meters": NEAREST_REGION_MAX_METERS,
            },
        ).scalar_one_or_none()

        if code is None:
            unmatched.append(place.name)
        else:
            place.nuts_code = code
            assigned += 1

    db.commit()
    return AssignmentResult(assigned, unmatched, countries)
