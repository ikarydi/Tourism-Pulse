from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class PulseSnapshot(Base):
    __tablename__ = "pulse_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)

    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.id"),
        nullable=False,
        index=True,
    )

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    pulse: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    demand: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    capacity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    events: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    environment: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    risk: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default="0",
    )

    economic: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default="0",
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    confidence_coverage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
