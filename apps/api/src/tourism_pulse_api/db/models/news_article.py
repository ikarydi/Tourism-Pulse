from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class NewsArticle(Base):
    """Silver layer: one GDELT article, individually queryable - unlike
    the aggregate news_mentions/news_sentiment Signal rows, which only
    ever say "how many" and "what average tone", never "which articles"
    or "about what". Full per-article metadata otherwise only survives
    inside the opaque raw JSON archived to SourceObservation (spec
    12.1's "never discard the source representation" is satisfied
    either way, but this makes it queryable/explainable on its own).

    `categories` is item_classifier.classify_item's output for this
    article's title, persisted so a place's article volume can be
    broken down by topic without re-running the classifier - see
    ingestion.gdelt.service.
    """

    __tablename__ = "news_articles"
    # (source, place_id, url) rather than just (source, url): the same
    # article URL can legitimately surface under more than one place's
    # query (e.g. an article mentioning both Budapest and Vienna), and
    # each place's ingestion run should get its own row rather than one
    # silently stealing the other's.
    __table_args__ = (UniqueConstraint("source", "place_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.id"),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(String(100), nullable=False)

    url: Mapped[str] = mapped_column(String(2048), nullable=False)

    title: Mapped[str] = mapped_column(String(1000), nullable=False)

    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # GDELT's TimelineTone tone reading is a per-query aggregate, not
    # per-article - nullable until/unless a per-article tone source
    # exists.
    tone: Mapped[float | None] = mapped_column(nullable=True)

    # List of item_classifier.ItemCategory values, e.g. ["risk"]. Empty
    # list, not null, when nothing matched (a real classification
    # result: "no specific topic", not "not yet classified").
    categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    source_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_observations.id"),
        nullable=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
