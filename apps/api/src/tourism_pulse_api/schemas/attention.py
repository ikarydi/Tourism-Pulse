from pydantic import BaseModel


class LanguageShareRead(BaseModel):
    language: str
    name: str
    views_12m: float
    share: float
    previous_share: float | None
    growth: float | None


class LeadRead(BaseModel):
    months: int
    correlation: float
    observations: int
    nights_place: str


class WikipediaInsightRead(BaseModel):
    latest_month: str
    latest_views: float
    latest_vs_last_year: float | None
    benchmark_vs_last_year: float | None
    relative_to_benchmark: float | None
    views_12m: float | None
    views_12m_vs_previous: float | None
    languages: list[LanguageShareRead]
    lead: LeadRead | None
    series: list[dict]


class TopicShareRead(BaseModel):
    topic: str
    label: str
    articles_12m: float
    share: float
    previous_share: float | None
    europe_share: float | None
    lift: float | None


class NewsInsightRead(BaseModel):
    latest_month: str
    attention_share: float | None
    attention_vs_last_year: float | None
    tourism_share: float | None
    tourism_articles_12m: float
    tone_3m: float | None
    tone_3m_last_year: float | None
    topics: list[TopicShareRead]
    series: list[dict]


class AttentionRead(BaseModel):
    place_id: int
    place_name: str
    wikipedia: WikipediaInsightRead | None
    news: NewsInsightRead | None
    highlights: list[str]


class AttentionSummaryRead(BaseModel):
    place_id: int
    name: str
    place_type: str
    country_code: str | None
    wiki_month: str | None
    wiki_vs_last_year: float | None
    wiki_relative: float | None
    language_gainer: str | None
    language_gain: float | None
    news_month: str | None
    news_vs_last_year: float | None
    tone_3m: float | None
    tone_change: float | None
    tourism_articles_12m: float
    top_topic: str | None
    top_topic_share: float | None
    top_topic_lift: float | None
    highlights: list[str]
