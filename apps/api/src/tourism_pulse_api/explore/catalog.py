"""The metric catalog - every number a user can chart, and how to get it.

Queries may only name metrics listed here (see query.py), so user input
never becomes SQL, and an LLM translating a question into a chart can
only pick from this list (see ask.py). Each metric knows its unit, its
native time grain and how to aggregate it into a coarser bucket.
"""

from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Signal

# Metric kinds, each answered by one query shape in query.py.
SNAPSHOT = "snapshot"  # pulse_snapshots column
SIGNAL = "signal"  # signals.value for one signal_type
INDICATOR = "indicator"  # regional_indicators via the place's NUTS 3/2 region
POPULATION = "population"  # place_demographics
COUNT = "count"  # rows in events / news_articles / video_items
STATIC = "static"  # one current value per place, no time axis


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    group: str
    unit: str
    grain: str  # native grain: "day" | "month" | "year" | "static"
    aggregation: str  # how to fold into a coarser bucket: "avg" | "sum"
    description: str
    kind: str
    source: str
    key: str  # column / signal_type / indicator / table, per kind

    def public(self) -> dict:
        data = asdict(self)
        data.pop("kind")
        data.pop("key")
        return data


_PULSE = "Tourism Pulse"
_OFFICIAL = "Official statistics"
_OBSERVATORY = "Pressure observatory"
_LIVE = "Live signals"
_SUPPLY = "Supply"
_MEDIA = "Media & events"
_ATTENTION = "Online attention"
_CULTURE = "Culture"

_STATIC_METRICS: list[Metric] = [
    *(
        Metric(
            id=f"pulse.{column}",
            label=label,
            group=_PULSE,
            unit="score (0-100)",
            grain="day",
            aggregation="avg",
            description=description,
            kind=SNAPSHOT,
            source="Tourism Pulse",
            key=column,
        )
        for column, label, description in (
            ("pulse", "Pulse score", "Overall Tourism Pulse composite, 0-100."),
            ("demand", "Demand", "Pulse demand dimension, 0-100."),
            ("capacity", "Capacity", "Pulse capacity dimension, 0-100."),
            ("events", "Events", "Pulse events dimension, 0-100."),
            ("environment", "Environment", "Pulse environment dimension, 0-100."),
            ("risk", "Risk", "Pulse risk dimension, 0-100 (higher = safer)."),
            ("economic", "Economic", "Pulse economic dimension, 0-100."),
            ("confidence_score", "Pulse confidence", "Confidence in the Pulse reading, 0-100."),
        )
    ),
    *(
        Metric(
            id=f"observatory.{indicator}",
            label=label,
            group=_OBSERVATORY,
            unit=unit,
            grain="year",
            aggregation="avg",
            description=description,
            kind=INDICATOR,
            source="Eurostat",
            key=indicator,
        )
        for indicator, label, unit, description in (
            (
                "tourism_intensity",
                "Tourism intensity",
                "nights per 1,000 residents",
                "Nights spent per 1,000 residents, for the place's NUTS 3 region (else NUTS 2).",
            ),
            (
                "tourism_density",
                "Tourism density",
                "nights per km²",
                "Nights spent per km² of the place's region.",
            ),
            (
                "seasonality_peak_share",
                "Peak-month concentration",
                "share of annual nights",
                "Share of the year's nights in its busiest month (even spread = 0.083).",
            ),
            (
                "str_share",
                "Short-term rental share",
                "share of nights",
                "Platform-booked nights as a share of platform plus official nights.",
            ),
        )
    ),
    Metric(
        id="observatory.pressure_score",
        label="Tourism pressure score",
        group=_OBSERVATORY,
        unit="score (0-100)",
        grain="static",
        aggregation="avg",
        description="Current pressure score: mean European percentile of the four indicators.",
        kind=STATIC,
        source="Eurostat",
        key="pressure_score",
    ),
    Metric(
        id="population",
        label="Population",
        group=_OFFICIAL,
        unit="residents",
        grain="year",
        aggregation="avg",
        description="Residents on 1 January.",
        kind=POPULATION,
        source="Eurostat",
        key="population",
    ),
    *(
        Metric(
            id=f"count.{table}",
            label=label,
            group=_MEDIA,
            unit="count",
            grain="day",
            aggregation="sum",
            description=description,
            kind=COUNT,
            source=source,
            key=table,
        )
        for table, label, source, description in (
            ("events", "Events", "Ticketmaster", "Number of events starting in the period."),
            ("news_articles", "News articles", "GDELT", "Articles published in the period."),
            ("video_items", "Videos", "YouTube", "Videos published in the period."),
        )
    ),
]

# signal_type -> (label, group, unit, grain, aggregation, description).
# Units are normalised in query.py (e.g. KSH thousand_nights -> nights).
_SIGNALS: dict[str, tuple[str, str, str, str, str, str]] = {
    "tourism_nights": (
        "Tourism nights",
        _OFFICIAL,
        "nights",
        "month",
        "sum",
        "Nights spent at tourist accommodation (Eurostat, KSH).",
    ),
    "occupancy_rate": (
        "Bed occupancy",
        _OFFICIAL,
        "percent",
        "month",
        "avg",
        "Net occupancy rate of bed places.",
    ),
    "tourist_arrivals": (
        "Tourist arrivals",
        _OFFICIAL,
        "arrivals",
        "month",
        "sum",
        "Arrivals at tourist accommodation.",
    ),
    "tourism_turnover_growth": (
        "Accommodation turnover growth",
        _OFFICIAL,
        "% year over year",
        "year",
        "avg",
        "Accommodation-sector net turnover, change on the previous year.",
    ),
    "visitor_pressure": (
        "Nights per resident",
        _OFFICIAL,
        "nights per resident",
        "month",
        "avg",
        "Tourism nights divided by resident population.",
    ),
    "accommodation_capacity": (
        "Bed places (monthly)",
        _SUPPLY,
        "bed places",
        "month",
        "avg",
        "Bed places at tourist accommodation.",
    ),
    "accommodation_capacity_annual": (
        "Bed places",
        _SUPPLY,
        "bed places",
        "year",
        "avg",
        "Bed places at tourist accommodation (annual).",
    ),
    "tourism_nights_annual": (
        "Tourism nights (annual)",
        _OFFICIAL,
        "nights",
        "year",
        "sum",
        "Nights spent at tourist accommodation in the year (Eurostat; regions and cities).",
    ),
    "platform_nights_annual": (
        "Platform-booked nights",
        _OFFICIAL,
        "nights",
        "year",
        "sum",
        "Nights booked through Airbnb, Booking.com, Expedia and Tripadvisor (Eurostat).",
    ),
    "nights_per_resident_annual": (
        "Nights per resident (city)",
        _OFFICIAL,
        "nights per resident",
        "year",
        "avg",
        "Tourist nights in the city per resident (Eurostat Urban Audit).",
    ),
    "domestic_nights_annual": (
        "Domestic guest nights",
        _OFFICIAL,
        "nights",
        "year",
        "sum",
        "Nights spent by residents of the same country (Eurostat Urban Audit).",
    ),
    "foreign_nights_annual": (
        "Foreign guest nights",
        _OFFICIAL,
        "nights",
        "year",
        "sum",
        "Nights spent by guests from abroad (Eurostat Urban Audit).",
    ),
    "museum_visitors_annual": (
        "Museum visitors",
        _CULTURE,
        "visitors",
        "year",
        "sum",
        "Museum visits in the city per year (Eurostat Urban Audit).",
    ),
    "wikipedia_views_monthly": (
        "Wikipedia views",
        _ATTENTION,
        "views",
        "month",
        "sum",
        "Monthly views of the place's Wikipedia articles (English and German; Hungarian "
        "areas also Hungarian).",
    ),
    "gdelt_tourism_share": (
        "Tourism news share",
        _ATTENTION,
        "per million articles",
        "month",
        "avg",
        "GDELT articles with a tourism theme that mention the country, per million articles.",
    ),
    "gdelt_tourism_tone": (
        "Tourism news tone",
        _ATTENTION,
        "tone",
        "month",
        "avg",
        "Average tone of those GDELT articles (negative = critical, positive = favourable).",
    ),
    "gdelt_attention_share": (
        "News attention share",
        _ATTENTION,
        "per million articles",
        "month",
        "avg",
        "GDELT articles on any topic that mention the area, per million articles.",
    ),
    **{
        f"{medium}_{category}_mentions": (
            f"{'News' if medium == 'news' else 'Video'} {category} mentions",
            _ATTENTION,
            "count",
            "day",
            "avg",
            f"{'GDELT articles' if medium == 'news' else 'YouTube videos'} about the place "
            f"classified as {category}.",
        )
        for medium in ("news", "video")
        for category in ("event", "risk", "economic")
    },
    "hotel_count": (
        "Hotels mapped",
        _SUPPLY,
        "count",
        "day",
        "avg",
        "Hotels in OpenStreetMap around the place.",
    ),
    "restaurant_count": (
        "Restaurants mapped",
        _SUPPLY,
        "count",
        "day",
        "avg",
        "Restaurants in OpenStreetMap around the place.",
    ),
    "weather_comfort": (
        "Weather comfort",
        _LIVE,
        "percent",
        "day",
        "avg",
        "Tourism weather comfort score (Open-Meteo).",
    ),
    "temperature": ("Temperature", _LIVE, "°C", "day", "avg", "Air temperature (Open-Meteo)."),
    "precipitation": ("Precipitation", _LIVE, "mm", "day", "avg", "Precipitation (Open-Meteo)."),
    "humidity": ("Humidity", _LIVE, "percent", "day", "avg", "Relative humidity (Open-Meteo)."),
    "wind_speed": ("Wind speed", _LIVE, "km/h", "day", "avg", "Wind speed (Open-Meteo)."),
    "airport_traffic": (
        "Aircraft nearby",
        _LIVE,
        "count",
        "day",
        "avg",
        "Aircraft in the air near the destination (OpenSky).",
    ),
    "search_interest": (
        "YouTube search results",
        _ATTENTION,
        "count",
        "day",
        "avg",
        "YouTube search results for the place.",
    ),
    "wikipedia_pageviews": (
        "Wikipedia views (30 days)",
        _ATTENTION,
        "views",
        "day",
        "avg",
        "Trailing 30-day Wikipedia pageviews.",
    ),
    "news_mentions": (
        "News mentions",
        _ATTENTION,
        "count",
        "day",
        "avg",
        "GDELT articles matching the place's tourism query.",
    ),
    "disaster_alert_severity": (
        "Disaster alert level",
        _LIVE,
        "alert score",
        "day",
        "avg",
        "Highest current GDACS alert for the country.",
    ),
}


# Stored source keys as readers know them.
_SOURCE_NAMES = {
    "eurostat": "Eurostat",
    "ksh": "KSH",
    "wikipedia": "Wikipedia",
    "gdelt": "GDELT",
    "youtube": "YouTube",
    "gdacs": "GDACS",
    "ticketmaster": "Ticketmaster",
    "open_meteo": "Open-Meteo",
    "openmeteo": "Open-Meteo",
    "open-meteo": "Open-Meteo",
    "opensky": "OpenSky",
    "osm": "OpenStreetMap",
    "google_trends": "Google Trends",
}


def _source_label(sources: list[str]) -> str:
    names = sorted({_SOURCE_NAMES.get(source, source) for source in sources})
    return " + ".join(names) if names else "signals"


def _signal_metric(signal_type: str, sources: list[str] | None = None) -> Metric:
    label, group, unit, grain, aggregation, description = _SIGNALS.get(
        signal_type,
        (
            signal_type.replace("_", " ").capitalize(),
            _LIVE,
            "value",
            "day",
            "avg",
            f"Signal {signal_type}.",
        ),
    )
    return Metric(
        id=f"signal.{signal_type}",
        label=label,
        group=group,
        unit=unit,
        grain=grain,
        aggregation=aggregation,
        description=description,
        kind=SIGNAL,
        source=_source_label(sources or []),
        key=signal_type,
    )


def build_catalog(db: Session) -> dict[str, Metric]:
    """Every chartable metric: the fixed ones plus a signal metric for each
    signal type actually stored (so the catalog never lists empty data)."""
    catalog = {metric.id: metric for metric in _STATIC_METRICS}
    sources: dict[str, list[str]] = {}
    for signal_type, source in db.query(Signal.signal_type, Signal.source).distinct():
        sources.setdefault(signal_type, []).append(source)
    for signal_type, found in sources.items():
        metric = _signal_metric(signal_type, found)
        catalog[metric.id] = metric
    return dict(sorted(catalog.items(), key=lambda item: (item[1].group, item[1].label)))
