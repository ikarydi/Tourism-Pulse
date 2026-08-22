from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class VideoItem(Base):
    """Silver layer: one YouTube search result, individually queryable -
    the video counterpart to NewsArticle, same reasoning (see that
    model's docstring). `categories` is item_classifier.classify_item's
    output for this video's title - see ingestion.youtube.service.
    """

    __tablename__ = "video_items"
    # (source, place_id, video_id) rather than just (source, video_id) -
    # same reasoning as NewsArticle's constraint.
    __table_args__ = (UniqueConstraint("source", "place_id", "video_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.id"),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(String(100), nullable=False)

    video_id: Mapped[str] = mapped_column(String(50), nullable=False)

    title: Mapped[str] = mapped_column(String(1000), nullable=False)

    channel: Mapped[str | None] = mapped_column(String(255), nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    source_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_observations.id"),
        nullable=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
