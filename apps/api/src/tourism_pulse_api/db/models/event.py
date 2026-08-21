from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        # Postgres treats NULL as distinct from NULL for uniqueness, so this
        # never conflicts with manually-created events (source/external_id
        # both NULL) - it only prevents duplicate ingestion of the same
        # event from the same external source.
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_events_source_external_id",
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

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2048),
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
