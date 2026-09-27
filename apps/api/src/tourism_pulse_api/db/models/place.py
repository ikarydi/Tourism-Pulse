from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tourism_pulse_api.db.base import Base

if TYPE_CHECKING:
    from tourism_pulse_api.db.models.destination import Destination


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)

    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # "country" | "destination" (hand-curated, live signals and Pulse) |
    # "region" (NUTS 2) | "area" (NUTS 3) | "city" (Eurostat Urban Audit).
    place_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Nullable and populated opportunistically - unlike weather/OSM
    # ingestion (which take coordinates as CLI args per run, deliberately
    # not tied to a stored place list), a map view needs a persisted point
    # per place to plot. Country-level places are left unset for now (no
    # single point represents a country well); city/resort destinations are
    # backfilled from the same coordinate list used to seed them.
    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Eurostat NUTS code of the place's statistical region: NUTS 2 for
    # destinations (assigned by point-in-polygon, see ingestion.nuts), the
    # national NUTS 0 code for countries. Not a foreign key - national
    # codes have no boundary row, and indicators are published for codes
    # whether or not a boundary is loaded.
    nuts_code: Mapped[str | None] = mapped_column(
        String(9),
        nullable=True,
    )

    # The NUTS 3 region containing a destination (None for countries).
    # The observatory prefers it wherever Eurostat publishes an indicator
    # at that finer level, falling back to nuts_code otherwise.
    nuts3_code: Mapped[str | None] = mapped_column(
        String(9),
        nullable=True,
    )

    # Stable identity for places generated from official geography
    # (ingestion.eu_locations): "NUTS2:HU11", "NUTS3:HU110",
    # "URAU:HU001C". None for hand-curated places.
    source_code: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
        index=True,
    )

    # Eurostat Urban Audit city code, linking the place to Eurostat's city
    # tourism statistics (urb_ctour). Set on generated city places and on
    # curated destinations matched to an Urban Audit city.
    urau_code: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
    )

    destination: Mapped["Destination"] = relationship(
        back_populates="places",
    )