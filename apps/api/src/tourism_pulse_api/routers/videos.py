from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, VideoItem
from tourism_pulse_api.db.session import get_db
from tourism_pulse_api.schemas.video_item import VideoItemRead

router = APIRouter(
    prefix="/places/{place_id}/videos",
    tags=["videos"],
)


@router.get(
    "",
    response_model=list[VideoItemRead],
)
def list_video_items(
    place_id: int,
    category: str | None = None,
    db: Session = Depends(get_db),
) -> list[VideoItem]:
    """Item-level YouTube search results (see ingestion.youtube.service.
    persist_videos) - the video counterpart to `news.list_news_articles`,
    same reasoning (read-only, Python-side category filter).
    """
    place = db.get(Place, place_id)

    if place is None:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    videos = (
        db.query(VideoItem)
        .filter(VideoItem.place_id == place_id)
        .order_by(
            VideoItem.published_at.desc().nullslast(),
            VideoItem.id.desc(),
        )
        .all()
    )

    if category is not None:
        videos = [video for video in videos if category in video.categories]

    return videos
