from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class SavedView(Base):
    """A user-built visualization: a catalog query plus how to draw it.

    `spec` holds {"query": {...}, "chart": {...}} as validated by
    schemas.explore.ViewSpec. Pinned views make up the dashboard, in
    `position` order. No owner column yet: there are no user accounts
    (spec section 27), so every view is shared.
    """

    __tablename__ = "saved_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
