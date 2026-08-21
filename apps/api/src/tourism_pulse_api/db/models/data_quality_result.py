from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class DataQualityResult(Base):
    """One recorded outcome of one data-quality check (spec section 14).

    Both passes and failures are persisted - not just rejections - so the
    table doubles as the "how reliable is it" half of spec section 13's
    governance questions, not only a rejection log.

    A rejected candidate's `source_observations` row is never altered or
    deleted (raw data is never discarded, spec section 12.1); only the
    `Signal` write is skipped. "Quarantined" is therefore a derived state:
    a `source_observations` row with a `severity="reject"` result here and
    no `Signal` row referencing it - not a separate status column that
    could drift out of sync with these rows.
    """

    __tablename__ = "data_quality_results"
    __table_args__ = (
        Index(
            "ix_data_quality_results_place_signal_checked",
            "place_id",
            "signal_type",
            "checked_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Nullable: a check can run before any observation row exists (e.g. a
    # source-failure check on an empty fetch response).
    source_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_observations.id"),
        nullable=True,
        index=True,
    )

    place_id: Mapped[int | None] = mapped_column(
        ForeignKey("places.id"),
        nullable=True,
        index=True,
    )

    signal_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    check_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    # "reject" (blocks the Signal write) or "warn" (recorded, does not
    # block). Only meaningful when passed is False.
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
