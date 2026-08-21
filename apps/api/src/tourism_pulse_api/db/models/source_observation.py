from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class SourceObservation(Base):
    """The Bronze layer (spec section 12): the exact payload a source
    adapter fetched, archived before any parsing/transformation happens.

    One row here can back many `Signal` rows (e.g. a single weather fetch
    produces several signals, a single KSH CSV backfill produces one per
    month) - the raw file/response is the true unit of evidence, per spec
    section 12.1 ("never discard the source representation").
    """

    __tablename__ = "source_observations"

    id: Mapped[int] = mapped_column(primary_key=True)

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id"),
        nullable=False,
        index=True,
    )

    # Disambiguates adapters that share one Source row, e.g. ksh and
    # ksh_capacity both fetch from source "ksh" but from different
    # STADAT datasets.
    dataset: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # Nullable: most fetches are place-scoped, but this table stays usable
    # for any future source that fetches across multiple places at once.
    place_id: Mapped[int | None] = mapped_column(
        ForeignKey("places.id"),
        nullable=True,
        index=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    # The exact fetched bytes, decoded as text - CSV or JSON uniformly,
    # disambiguated by content_type below.
    raw_payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # sha256 hex digest of raw_payload, computed at archive time (spec
    # section 12.4).
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # Adapter-supplied tag for schema-change detection (spec section 14).
    schema_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
