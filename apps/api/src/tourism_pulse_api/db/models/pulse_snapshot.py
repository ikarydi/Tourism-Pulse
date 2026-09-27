from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Text
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

    # Tourism-pressure score from the observatory (observatory.pressure),
    # reported beside the Pulse. Nullable: a place without regional data
    # has no reading, and older snapshots predate it.
    pressure: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    confidence_coverage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # LLM-written analyst narrative (pulse.narrative) - nullable: no LLM
    # provider configured (settings.groq_api_key unset), or generation
    # failed, or this snapshot predates the feature entirely.
    narrative: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
