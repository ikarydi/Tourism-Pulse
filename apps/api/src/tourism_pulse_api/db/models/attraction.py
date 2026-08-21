from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class Attraction(Base):
    __tablename__ = "attractions"
    __table_args__ = (
        # Same pattern as Event: NULL/NULL never conflicts with manually
        # created attractions, only prevents re-ingesting the same OSM
        # element as a duplicate row on repeated ingestion runs.
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_attractions_source_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
