from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base
from tourism_pulse_api.db.types import Geometry


class NutsRegion(Base):
    """Eurostat NUTS region boundary (reference geography, not a Signal).

    Loaded from GISCO by ingestion.nuts so each destination can be placed
    in its official statistical region with a PostGIS point-in-polygon
    query - that region's code is what Eurostat's regional tourism
    indicators are published under (see RegionalIndicator).
    """

    __tablename__ = "nuts_regions"
    __table_args__ = (Index("ix_nuts_regions_geom", "geom", postgresql_using="gist"),)

    code: Mapped[str] = mapped_column(String(9), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nuts_version: Mapped[str] = mapped_column(String(10), nullable=False)
    geom: Mapped[object] = mapped_column(Geometry("MultiPolygon", 4326), nullable=False)
