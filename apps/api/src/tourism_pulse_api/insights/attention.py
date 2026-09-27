"""Online-attention insights for curated places, from stored monthly data.

Wikipedia: how interest compares with a year ago, which language editions
(read as source markets) are growing, and whether interest has led the
place's official nights. GDELT: how much international news mentions the
place, the tone of its tourism coverage, and which topics its tourism
coverage carries more often than European tourism coverage overall.

Every number is computed from stored series; the plain-language highlights
are built from those numbers, not by a language model.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place, Signal, SignalBreakdown

WIKI = "wikipedia_views_monthly"
TOPICS = "gdelt_tourism_articles"
NIGHTS = "tourism_nights"
COVID = (pd.Period("2020-03", "M"), pd.Period("2021-12", "M"))

LANGUAGE_NAMES = {
    "en": "English", "de": "German", "fr": "French", "it": "Italian", "es": "Spanish",
    "nl": "Dutch", "pl": "Polish", "pt": "Portuguese", "sv": "Swedish", "da": "Danish",
    "fi": "Finnish", "cs": "Czech", "hu": "Hungarian", "ro": "Romanian", "el": "Greek",
    "ru": "Russian", "uk": "Ukrainian", "tr": "Turkish", "ar": "Arabic", "he": "Hebrew",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "bg": "Bulgarian", "et": "Estonian",
    "hr": "Croatian", "lt": "Lithuanian", "lb": "Luxembourgish", "lv": "Latvian",
    "mt": "Maltese", "sk": "Slovak", "sl": "Slovenian",
}  # fmt: skip
TOPIC_LABELS = {
    "protest": "Protests",
    "strike": "Strikes",
    "security": "Crime and security",
    "disaster": "Disasters and extreme weather",
    "climate": "Climate change",
    "health": "Health and disease",
    "prices": "Prices and inflation",
    "housing": "Housing",
    "air_travel": "Airports and air travel",
    "heritage": "Culture and heritage",
}
# Shares and lifts below these volumes are too noisy to report.
MIN_TOPIC_ARTICLES = 40
MIN_LANGUAGE_SHARE = 0.01
MIN_LEAD_MONTHS = 24
MIN_LEAD_CORRELATION = 0.3


def in_covid(month: pd.Period) -> bool:
    return COVID[0] <= month <= COVID[1]


def monthly(db: Session, place_ids: list[int], signal_type: str) -> dict[int, pd.Series]:
    rows = (
        db.query(Signal.place_id, Signal.observed_at, Signal.value, Signal.unit)
        .filter(Signal.signal_type == signal_type, Signal.place_id.in_(place_ids))
        .all()
    )
    grouped: dict[int, dict[pd.Period, list[float]]] = {}
    for place_id, observed_at, value, unit in rows:
        factor = 1000.0 if unit == "thousand_nights" else 1.0
        grouped.setdefault(place_id, {}).setdefault(pd.Period(observed_at, "M"), []).append(
            float(value) * factor
        )
    return {
        place_id: pd.Series({m: sum(v) / len(v) for m, v in months.items()}).sort_index()
        for place_id, months in grouped.items()
    }


def breakdown(db: Session, place_ids: list[int], signal_type: str) -> pd.DataFrame:
    rows = (
        db.query(
            SignalBreakdown.place_id,
            SignalBreakdown.observed_at,
            SignalBreakdown.key,
            SignalBreakdown.value,
        )
        .filter(SignalBreakdown.signal_type == signal_type, SignalBreakdown.place_id.in_(place_ids))
        .all()
    )
    frame = pd.DataFrame(rows, columns=["place_id", "observed_at", "key", "value"])
    if frame.empty:
        return frame
    frame["month"] = [pd.Period(value, "M") for value in frame["observed_at"]]
    frame["value"] = frame["value"].astype(float)
    return frame


def change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return current / previous - 1


def window_sum(series: pd.Series, last: pd.Period, months: int) -> float | None:
    window = series[(series.index > last - months) & (series.index <= last)]
    return float(window.sum()) if len(window) == months else None


def period_label(month: pd.Period) -> str:
    return month.strftime("%B %Y")


def percent(value: float) -> str:
    return f"{value * 100:+.0f}%"


# --- Wikipedia --------------------------------------------------------------------


@dataclass
class LanguageShare:
    language: str
    name: str
    views_12m: float
    share: float
    previous_share: float | None
    growth: float | None


@dataclass
class Lead:
    months: int
    correlation: float
    observations: int
    nights_place: str


@dataclass
class WikipediaInsight:
    latest_month: str
    latest_views: float
    latest_vs_last_year: float | None
    # The median change across all curated places in the same month:
    # Wikipedia's own traffic has been falling since 2024, so a place's
    # change only means something against this.
    benchmark_vs_last_year: float | None
    relative_to_benchmark: float | None
    views_12m: float | None
    views_12m_vs_previous: float | None
    languages: list[LanguageShare] = field(default_factory=list)
    lead: Lead | None = None
    series: list[dict] = field(default_factory=list)


def language_mix(frame: pd.DataFrame, last: pd.Period) -> list[LanguageShare]:
    """Views per language edition over the last 12 months and the 12 before."""
    if frame.empty:
        return []
    current = frame[(frame["month"] > last - 12) & (frame["month"] <= last)]
    previous = frame[(frame["month"] > last - 24) & (frame["month"] <= last - 12)]
    now = current.groupby("key")["value"].sum()
    before = previous.groupby("key")["value"].sum()
    total_now, total_before = float(now.sum()), float(before.sum())
    if total_now <= 0:
        return []
    shares = []
    for language, views in now.sort_values(ascending=False).items():
        previous_views = float(before.get(language, 0.0))
        shares.append(
            LanguageShare(
                language=str(language),
                name=LANGUAGE_NAMES.get(str(language), str(language)),
                views_12m=float(views),
                share=float(views) / total_now,
                previous_share=previous_views / total_before if total_before > 0 else None,
                growth=change(float(views), previous_views),
            )
        )
    return shares


def lead_lag(
    views: pd.Series, nights: pd.Series, *, max_lag: int = 6
) -> tuple[int, float, int] | None:
    """The lag (months) at which year-on-year growth in views best matches
    later year-on-year growth in nights, outside COVID-touched months."""
    with np.errstate(divide="ignore", invalid="ignore"):
        g_views = np.log(views.where(views > 0)).diff(12)
        g_nights = np.log(nights.where(nights > 0)).diff(12)
    best = None
    for lag in range(max_lag + 1):
        shifted = g_views.shift(lag)
        joined = pd.concat([shifted.rename("v"), g_nights.rename("n")], axis=1).dropna()
        clean = [
            m
            for m in joined.index
            if not any(in_covid(x) or in_covid(x - 12) for x in (m, m - lag))
        ]
        joined = joined.loc[clean]
        if len(joined) < MIN_LEAD_MONTHS:
            continue
        correlation = float(np.corrcoef(joined["v"], joined["n"])[0, 1])
        if best is None or correlation > best[1]:
            best = (lag, correlation, len(joined))
    return best


# --- GDELT ------------------------------------------------------------------------


@dataclass
class TopicShare:
    topic: str
    label: str
    articles_12m: float
    share: float
    previous_share: float | None
    europe_share: float | None
    lift: float | None


@dataclass
class NewsInsight:
    latest_month: str
    attention_share: float | None
    attention_vs_last_year: float | None
    tourism_share: float | None
    tourism_articles_12m: float
    tone_3m: float | None
    tone_3m_last_year: float | None
    topics: list[TopicShare] = field(default_factory=list)
    series: list[dict] = field(default_factory=list)


def topic_shares(
    place: pd.DataFrame, europe: pd.DataFrame, last: pd.Period
) -> tuple[float, list[TopicShare]]:
    """Share of the place's tourism articles touching each topic (last 12
    months, and the 12 before), and the same share across all 27 countries'
    tourism coverage."""

    def totals(frame: pd.DataFrame, first: pd.Period, end: pd.Period) -> pd.Series:
        window = frame[(frame["month"] > first) & (frame["month"] <= end)]
        return window.groupby("key")["value"].sum()

    now = totals(place, last - 12, last)
    before = totals(place, last - 24, last - 12)
    europe_now = totals(europe, last - 12, last) if not europe.empty else pd.Series(dtype=float)
    articles = float(now.get("all", 0.0))
    if articles <= 0:
        return 0.0, []
    shares = []
    for topic, label in TOPIC_LABELS.items():
        count = float(now.get(topic, 0.0))
        share = count / articles
        previous_all = float(before.get("all", 0.0))
        previous = float(before.get(topic, 0.0)) / previous_all if previous_all > 0 else None
        europe_all = float(europe_now.get("all", 0.0))
        europe_share = float(europe_now.get(topic, 0.0)) / europe_all if europe_all > 0 else None
        shares.append(
            TopicShare(
                topic=topic,
                label=label,
                articles_12m=count,
                share=share,
                previous_share=previous,
                europe_share=europe_share,
                lift=share / europe_share if europe_share else None,
            )
        )
    shares.sort(key=lambda item: item.share, reverse=True)
    return articles, shares


# --- per place ----------------------------------------------------------------------


@dataclass
class AttentionInsight:
    place_id: int
    place_name: str
    wikipedia: WikipediaInsight | None
    news: NewsInsight | None
    highlights: list[str]


def nights_series_for(db: Session, place: Place) -> tuple[str, pd.Series] | None:
    """The place's own monthly nights, else its NUTS 2 region's."""
    own = monthly(db, [place.id], NIGHTS).get(place.id)
    if own is not None and own.count() >= MIN_LEAD_MONTHS + 12:
        return place.name, own
    if place.place_type == "destination" and place.nuts_code:
        region = (
            db.query(Place)
            .filter(Place.place_type == "region", Place.nuts_code == place.nuts_code)
            .first()
        )
        if region is not None:
            series = monthly(db, [region.id], NIGHTS).get(region.id)
            if series is not None and series.count() >= MIN_LEAD_MONTHS + 12:
                return region.name, series
    return None


def europe_topics(db: Session) -> pd.DataFrame:
    country_ids = [pid for (pid,) in db.query(Place.id).filter(Place.place_type == "country")]
    return breakdown(db, country_ids, TOPICS)


def wikipedia_benchmark(db: Session, month: pd.Period) -> float | None:
    """Median year-on-year change in Wikipedia views across curated places."""
    curated = [
        pid
        for (pid,) in db.query(Place.id).filter(Place.place_type.in_(("country", "destination")))
    ]
    changes = []
    for series in monthly(db, curated, WIKI).values():
        now, before = series.get(month), series.get(month - 12)
        if now is not None and before is not None and before > 0:
            changes.append(now / before - 1)
    return float(np.median(changes)) if len(changes) >= 10 else None


def wikipedia_insight(
    db: Session, place: Place, benchmark: dict[pd.Period, float | None] | None = None
) -> WikipediaInsight | None:
    views = monthly(db, [place.id], WIKI).get(place.id)
    if views is None or views.empty:
        return None
    last = views.index.max()
    latest = float(views[last])
    last_year = views.get(last - 12)
    views_12m = window_sum(views, last, 12)
    previous_12m = window_sum(views, last - 12, 12)
    own = change(latest, float(last_year) if last_year is not None else None)
    if benchmark is not None and last in benchmark:
        typical = benchmark[last]
    else:
        typical = wikipedia_benchmark(db, last)
    insight = WikipediaInsight(
        latest_month=str(last),
        latest_views=latest,
        latest_vs_last_year=own,
        benchmark_vs_last_year=typical,
        relative_to_benchmark=(
            (1 + own) / (1 + typical) - 1 if own is not None and typical is not None else None
        ),
        views_12m=views_12m,
        views_12m_vs_previous=change(views_12m, previous_12m),
        languages=language_mix(breakdown(db, [place.id], WIKI), last),
        series=[
            {"period": str(m), "value": float(v)} for m, v in views[views.index > last - 36].items()
        ],
    )
    nights = nights_series_for(db, place)
    if nights is not None:
        found = lead_lag(views, nights[1])
        if found is not None:
            months, correlation, observations = found
            insight.lead = Lead(months, correlation, observations, nights[0])
    return insight


def news_insight(db: Session, place: Place, europe: pd.DataFrame) -> NewsInsight | None:
    attention = monthly(db, [place.id], "gdelt_attention_share").get(place.id)
    tone = monthly(db, [place.id], "gdelt_tourism_tone").get(place.id)
    tourism = monthly(db, [place.id], "gdelt_tourism_share").get(place.id)
    topics = breakdown(db, [place.id], TOPICS)
    if attention is None and tourism is None:
        return None
    reference = attention if attention is not None else tourism
    assert reference is not None
    last = reference.index.max()

    def mean_over(series: pd.Series | None, end: pd.Period, months: int) -> float | None:
        if series is None:
            return None
        window = series[(series.index > end - months) & (series.index <= end)]
        return float(window.mean()) if len(window) else None

    articles, shares = topic_shares(topics, europe, last) if not topics.empty else (0.0, [])
    latest_attention = (
        float(attention[last]) if attention is not None and last in attention else None
    )
    return NewsInsight(
        latest_month=str(last),
        attention_share=latest_attention,
        attention_vs_last_year=change(
            mean_over(attention, last, 3), mean_over(attention, last - 12, 3)
        ),
        tourism_share=float(tourism[last]) if tourism is not None and last in tourism else None,
        tourism_articles_12m=articles,
        tone_3m=mean_over(tone, last, 3),
        tone_3m_last_year=mean_over(tone, last - 12, 3),
        topics=shares,
        series=[
            {
                "period": str(m),
                "attention_share": float(v),
                "tone": float(tone[m]) if tone is not None and m in tone else None,
            }
            for m, v in attention.items()
            if m > last - 36
        ]
        if attention is not None
        else [],
    )


def highlights(wiki: WikipediaInsight | None, news: NewsInsight | None) -> list[str]:
    out = []
    if wiki is not None:
        month = period_label(pd.Period(wiki.latest_month, "M"))
        if wiki.relative_to_benchmark is not None and wiki.latest_vs_last_year is not None:
            relative = wiki.relative_to_benchmark
            verdict = (
                "held up better than most places"
                if relative >= 0.05
                else "fell behind most places"
                if relative <= -0.05
                else "moved in line with most places"
            )
            out.append(
                f"Wikipedia interest in {month}: {percent(wiki.latest_vs_last_year)} on a year "
                f"earlier, against {percent(wiki.benchmark_vs_last_year or 0)} for the median "
                f"tracked place, so it {verdict} ({percent(relative)} relative)."
            )
        shifting = [
            item
            for item in wiki.languages
            if item.share >= MIN_LANGUAGE_SHARE and item.previous_share is not None
        ]
        if shifting:
            gainer = max(shifting, key=lambda item: item.share - (item.previous_share or 0))
            gain = gainer.share - (gainer.previous_share or 0)
            if gain >= 0.02:
                out.append(
                    f"{gainer.name}-language editions gained the most ground over the last "
                    f"12 months: {gainer.previous_share:.0%} → {gainer.share:.0%} of views."
                )
        if wiki.lead is not None and wiki.lead.correlation >= MIN_LEAD_CORRELATION:
            if wiki.lead.months == 0:
                out.append(
                    f"Interest moves with {wiki.lead.nights_place}'s official nights in the same "
                    f"month (correlation {wiki.lead.correlation:.2f} over "
                    f"{wiki.lead.observations} months)."
                )
            else:
                out.append(
                    f"Interest has led {wiki.lead.nights_place}'s official nights by "
                    f"{wiki.lead.months} month{'s' if wiki.lead.months > 1 else ''} "
                    f"(correlation {wiki.lead.correlation:.2f} over "
                    f"{wiki.lead.observations} months)."
                )
    if news is not None:
        if news.attention_vs_last_year is not None:
            out.append(
                f"International news mentions over the last three months: "
                f"{percent(news.attention_vs_last_year)} against a year earlier."
            )
        if news.tone_3m is not None and news.tone_3m_last_year is not None:
            shift = news.tone_3m - news.tone_3m_last_year
            if abs(shift) >= 0.5:
                direction = "more positive" if shift > 0 else "more negative"
                out.append(
                    f"The tone of its tourism coverage turned {direction} "
                    f"({news.tone_3m:+.1f} against {news.tone_3m_last_year:+.1f} a year earlier)."
                )
        if news.tourism_articles_12m >= MIN_TOPIC_ARTICLES:
            standouts = [
                topic
                for topic in news.topics
                if topic.lift is not None and topic.lift >= 1.5 and topic.articles_12m >= 10
            ]
            for topic in sorted(standouts, key=lambda t: t.lift or 0, reverse=True)[:2]:
                out.append(
                    f"{topic.label} featured in {topic.share:.0%} of its tourism coverage over "
                    f"the last 12 months, {topic.lift:.1f}× the European average."
                )
    return out


def attention_for_place(db: Session, place: Place) -> AttentionInsight:
    wiki = wikipedia_insight(db, place)
    news = news_insight(db, place, europe_topics(db))
    return AttentionInsight(
        place_id=place.id,
        place_name=place.name,
        wikipedia=wiki,
        news=news,
        highlights=highlights(wiki, news),
    )


def summary_row(place: Place, insight: AttentionInsight) -> dict:
    """One line per place for the cross-place attention table."""
    wiki, news = insight.wikipedia, insight.news
    gainer = None
    if wiki is not None:
        shifting = [
            item
            for item in wiki.languages
            if item.share >= MIN_LANGUAGE_SHARE and item.previous_share is not None
        ]
        if shifting:
            gainer = max(shifting, key=lambda item: item.share - (item.previous_share or 0))
    top = None
    if news is not None and news.tourism_articles_12m >= MIN_TOPIC_ARTICLES:
        candidates = [t for t in news.topics if t.lift is not None and t.articles_12m >= 10]
        if candidates:
            top = max(candidates, key=lambda t: t.lift or 0)
    return {
        "place_id": place.id,
        "name": place.name,
        "place_type": place.place_type,
        "country_code": place.destination.country_code if place.destination else None,
        "wiki_month": wiki.latest_month if wiki else None,
        "wiki_vs_last_year": wiki.latest_vs_last_year if wiki else None,
        "wiki_relative": wiki.relative_to_benchmark if wiki else None,
        "language_gainer": gainer.name if gainer else None,
        "language_gain": (gainer.share - (gainer.previous_share or 0)) if gainer else None,
        "news_month": news.latest_month if news else None,
        "news_vs_last_year": news.attention_vs_last_year if news else None,
        "tone_3m": news.tone_3m if news else None,
        "tone_change": (
            news.tone_3m - news.tone_3m_last_year
            if news and news.tone_3m is not None and news.tone_3m_last_year is not None
            else None
        ),
        "tourism_articles_12m": news.tourism_articles_12m if news else 0.0,
        "top_topic": top.label if top else None,
        "top_topic_share": top.share if top else None,
        "top_topic_lift": top.lift if top else None,
        "highlights": insight.highlights,
    }


def attention_overview(db: Session) -> list[dict]:
    """Every curated place's attention summary, sharing one Wikipedia
    benchmark per month and one European topic baseline."""
    places = (
        db.query(Place)
        .filter(Place.place_type.in_(("country", "destination")))
        .order_by(Place.name)
        .all()
    )
    europe = europe_topics(db)
    benchmark: dict[pd.Period, float | None] = {}
    rows = []
    for place in places:
        views = monthly(db, [place.id], WIKI).get(place.id)
        if views is not None and not views.empty:
            last = views.index.max()
            if last not in benchmark:
                benchmark[last] = wikipedia_benchmark(db, last)
        wiki = wikipedia_insight(db, place, benchmark)
        news = news_insight(db, place, europe)
        insight = AttentionInsight(place.id, place.name, wiki, news, highlights(wiki, news))
        rows.append(summary_row(place, insight))
    return rows
