from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "signal_type",
            "observed_at",
            "source",
            name="uq_signals_place_type_observed_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.id"),
        nullable=False,
    )

    signal_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    value: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )

    unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
