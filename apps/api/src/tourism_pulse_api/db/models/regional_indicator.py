from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class RegionalIndicator(Base):
    """One official tourism-pressure indicator value for one NUTS region
    and year - the tourism-pressure observatory's dataset.

    Reference data, like PlaceDemographics: stored for *every* region
    Eurostat publishes, not only regions containing a tracked place, so
    a destination can be ranked against all of Europe. Keyed by NUTS
    code rather than place (see Place.nuts_code for the link).
    """

    __tablename__ = "regional_indicators"
    __table_args__ = (UniqueConstraint("nuts_code", "indicator", "year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nuts_code: Mapped[str] = mapped_column(String(9), nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_observations.id"),
        nullable=True,
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
