"""Column types SQLAlchemy doesn't ship with.

`Geometry` maps a PostGIS geometry column without pulling in
GeoAlchemy2: the ORM never reads or writes geometry values itself -
loaders insert with ST_GeomFromGeoJSON and spatial queries run in SQL -
so the column only needs to exist with the right PostGIS type.
"""

from sqlalchemy.types import UserDefinedType


class Geometry(UserDefinedType):
    cache_ok = True

    def __init__(self, geometry_type: str = "MultiPolygon", srid: int = 4326) -> None:
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **kw: object) -> str:
        return f"geometry({self.geometry_type}, {self.srid})"
