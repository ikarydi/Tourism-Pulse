from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class Source(Base):
    """The system-of-record for source reliability (spec section 6.5/13).

    Replaces the hardcoded ``pulse.reliability.SOURCE_RELIABILITY`` dict as
    the primary reliability lookup - that dict is not deleted, it stays as
    the seed data for this table's initial migration and as a fallback for
    any source name that has not been registered here yet (see
    ``pulse.source_registry``).
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reliability: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
    )

    base_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # False for sources that are registered (so the rest of the pipeline -
    # migrations, adapter scaffolds - can already reference them) but not
    # yet actually wired to a live fetch, e.g. Booking.com/Airbnb.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
