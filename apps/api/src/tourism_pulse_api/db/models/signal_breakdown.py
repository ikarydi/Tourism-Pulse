from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class SignalBreakdown(Base):
    """One part of a monthly signal, split along one dimension.

    Wikipedia views by language edition (dimension "language", key "de")
    and GDELT tourism coverage by topic (dimension "topic", key "protest")
    live here, next to the total kept in `signals`. Keeping the parts out of
    `signals` stops them being summed or averaged into the total by the
    query engine, and keeps the metric catalog from growing one entry per
    language.
    """

    __tablename__ = "signal_breakdowns"
    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "signal_type",
            "observed_at",
            "dimension",
            "key",
            name="uq_signal_breakdowns_place_type_observed_dimension_key",
        ),
        Index("ix_signal_breakdowns_place_type_dimension", "place_id", "signal_type", "dimension"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), nullable=False)
    # The total's signal_type in `signals`, e.g. "wikipedia_views_monthly".
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
