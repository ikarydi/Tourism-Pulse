from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import NewsArticle, Place
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.news_article import NewsArticleRead

router = APIRouter(
    prefix="/places/{place_id}/news",
    tags=["news"],
)


@router.get(
    "",
    response_model=list[NewsArticleRead],
)
def list_news_articles(
    place_id: int,
    category: str | None = None,
    db: Session = Depends(get_db),
) -> list[NewsArticle]:
    """Item-level GDELT articles (see ingestion.gdelt.service.persist_articles)
    - the drill-down behind the aggregate news_mentions/news_sentiment
    signals. Read-only: rows are written only by ingestion adapters, never
    via this API.

    `category` filters by classification.item_classifier.ItemCategory
    value (e.g. "risk"). Filtered in Python, not SQL: `categories` is a
    portable generic JSON column (not Postgres-specific JSONB), which has
    no reliable cross-dialect "array contains" query operator - row counts
    per place are small enough that this costs nothing in practice.
    """
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.place_id == place_id)
        .order_by(
            NewsArticle.published_at.desc().nullslast(),
            NewsArticle.id.desc(),
        )
        .all()
    )

    if category is not None:
        articles = [article for article in articles if category in article.categories]

    return articles
