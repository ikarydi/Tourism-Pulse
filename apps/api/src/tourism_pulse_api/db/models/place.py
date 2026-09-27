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

    place_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
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

    destination: Mapped["Destination"] = relationship(
        back_populates="places",
    )