import json

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from tourism_pulse_api.db.session import get_db

router = APIRouter(prefix="/regions", tags=["regions"])

# Simplification tolerance in degrees per level: plenty for a web map of
# Europe, and turns ~45 MB of 1:1M boundaries into a few MB.
_TOLERANCE = {2: 0.01, 3: 0.006}

_REGION_SHAPES = text(
    """
    SELECT r.code, r.name, p.id AS place_id,
           ST_AsGeoJSON(ST_SimplifyPreserveTopology(r.geom, :tolerance), 4) AS geometry
    FROM nuts_regions r
    JOIN places p ON p.source_code = :prefix || r.code
    WHERE r.level = :level
    ORDER BY r.code
    """
)

# Boundaries change once per NUTS revision: build each level's
# FeatureCollection once per process.
_cache: dict[int, bytes] = {}


@router.get("/geojson")
def get_region_shapes(
    level: int = Query(2, ge=2, le=3),
    db: Session = Depends(get_db),
) -> Response:
    """Simplified NUTS 2 / NUTS 3 boundaries of every region that is a
    place, with its place id - for choropleth maps."""
    if level not in _cache:
        rows = db.execute(
            _REGION_SHAPES,
            {"tolerance": _TOLERANCE[level], "prefix": f"NUTS{level}:", "level": level},
        )
        features = [
            {
                "type": "Feature",
                "properties": {"code": code, "name": name, "place_id": place_id},
                "geometry": json.loads(geometry),
            }
            for code, name, place_id, geometry in rows
        ]
        _cache[level] = json.dumps(
            {"type": "FeatureCollection", "features": features}, separators=(",", ":")
        ).encode()
    return Response(
        content=_cache[level],
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=86400"},
    )
