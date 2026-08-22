from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class PlaceDemographics(Base):
    """Reference data, not a Signal - population doesn't represent a
    tourism-activity reading the way Signal.value does, so it never
    flows through the data-quality gate or feeds a Pulse dimension
    directly (see ingestion.eurostat's population metric). It exists so
    a derived metric (visitor_pressure - tourism_nights per resident,
    see eurostat/service.py) has a resident-population denominator to
    divide by, and so the number itself is queryable/explainable on its
    own (spec section 12.1: never discard the source representation).
    """

    __tablename__ = "place_demographics"
    __table_args__ = (UniqueConstraint("place_id", "year"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.id"),
        nullable=False,
        index=True,
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False)

    population: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[str] = mapped_column(String(100), nullable=False)

    source_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_observations.id"),
        nullable=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
