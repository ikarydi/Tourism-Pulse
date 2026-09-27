from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base

LIVE = "live"
BACKTEST = "backtest"


class Forecast(Base):
    """A forecast of one month of an official series, as issued.

    kind "live": issued on `issued_at` from the data known then. Written
    once per (place, series, origin, target) and never updated, so the
    track record cannot be rewritten after the official figure lands.
    kind "backtest": what the same method would have issued at a past
    origin, recomputable, and always shown as such.
    """

    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "signal_type",
            "kind",
            "origin",
            "target",
            name="uq_forecasts_place_type_kind_origin_target",
        ),
        Index("ix_forecasts_place_type_kind", "place_id", "signal_type", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Month ends, like signals.observed_at: the last official month used,
    # and the month forecast.
    origin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    point: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    low_80: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    high_80: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    low_95: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    high_95: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
