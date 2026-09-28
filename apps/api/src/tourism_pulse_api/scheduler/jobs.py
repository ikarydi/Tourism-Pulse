"""Per-adapter job definitions for the ingestion scheduler.

Each `ScheduledAdapter` names an adapter's `run(argv)` entrypoint
(every adapter already exposes exactly that - see e.g.
ingestion.weather.__main__.run - designed to be called in-process, not
shelled out to), how often to run it, and a `build_argv` function that
turns the current `places`/`destinations` tables into one argv list per
eligible place for that adapter.

Routing is derived from data already on Place/Destination (name, lat/
lon, country_code, place_type) rather than a hardcoded per-place table:
Wikipedia's article title, YouTube/GDELT's search query, and events'
city name are all built from `Place.name`; KSH/Eurostat/GDACS/events'
country scoping comes from `Destination.country_code`. A place missing
what an adapter needs (no coordinates for a lat/lon-driven source, a
name that isn't one of KSH's supported tourism areas, no country code)
is skipped for that adapter, not guessed at.

Only curated places (destinations and countries) get live adapters. The
EU-wide regions, areas and cities are official-statistics places, loaded in
bulk by eurostat_bulk; scheduling every live source for ~2,000 of them would
spend API quotas on places that have no Pulse.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.forecasting.__main__ import run as run_forecasting
from tourism_pulse_api.ingestion.ec_survey.__main__ import run as run_ec_survey
from tourism_pulse_api.ingestion.eurocontrol.__main__ import run as run_eurocontrol
from tourism_pulse_api.ingestion.eurostat.__main__ import run as run_eurostat
from tourism_pulse_api.ingestion.eurostat.parser import eurostat_geo_code
from tourism_pulse_api.ingestion.eurostat_bulk.__main__ import run as run_eurostat_bulk
from tourism_pulse_api.ingestion.eurostat_regional.__main__ import run as run_eurostat_regional
from tourism_pulse_api.ingestion.events.__main__ import run as run_events
from tourism_pulse_api.ingestion.gdacs.__main__ import run as run_gdacs
from tourism_pulse_api.ingestion.gdelt.__main__ import run as run_gdelt
from tourism_pulse_api.ingestion.gdelt_gkg.__main__ import run as run_gdelt_gkg
from tourism_pulse_api.ingestion.ksh.__main__ import run as run_ksh
from tourism_pulse_api.ingestion.ksh.parser import SUPPORTED_REGIONS as KSH_SUPPORTED_REGIONS
from tourism_pulse_api.ingestion.ksh_capacity.__main__ import run as run_ksh_capacity
from tourism_pulse_api.ingestion.openaq.__main__ import run as run_openaq
from tourism_pulse_api.ingestion.opensky.__main__ import run as run_opensky
from tourism_pulse_api.ingestion.osm.__main__ import run as run_osm
from tourism_pulse_api.ingestion.weather.__main__ import run as run_weather
from tourism_pulse_api.ingestion.wikipedia.__main__ import run as run_wikipedia
from tourism_pulse_api.ingestion.wikipedia_monthly.__main__ import run as run_wikipedia_monthly
from tourism_pulse_api.ingestion.youtube.__main__ import run as run_youtube

RunFn = Callable[[list[str] | None], int]
ArgvBuilder = Callable[[Session], list[list[str]]]


@dataclass(frozen=True)
class ScheduledAdapter:
    name: str
    run: RunFn
    build_argv: ArgvBuilder
    interval_minutes: int


CURATED_PLACE_TYPES = ("destination", "country")


def _curated_places(db: Session) -> list[Place]:
    return db.query(Place).filter(Place.place_type.in_(CURATED_PLACE_TYPES)).all()


def _places_with_coordinates(db: Session) -> list[Place]:
    return (
        db.query(Place)
        .filter(
            Place.place_type.in_(CURATED_PLACE_TYPES),
            Place.latitude.isnot(None),
            Place.longitude.isnot(None),
        )
        .all()
    )


def _country_places(db: Session) -> list[Place]:
    return db.query(Place).filter(Place.place_type == "country").all()


# --- weather / OSM / OpenAQ: lat/lon-driven ---------------------------------


def build_argv_weather(db: Session) -> list[list[str]]:
    return [
        ["--place-id", str(place.id), "--lat", str(place.latitude), "--lon", str(place.longitude)]
        for place in _places_with_coordinates(db)
    ]


def build_argv_osm(db: Session) -> list[list[str]]:
    return [
        ["--place-id", str(place.id), "--lat", str(place.latitude), "--lon", str(place.longitude)]
        for place in _places_with_coordinates(db)
    ]


def build_argv_openaq(db: Session) -> list[list[str]]:
    return [
        ["--place-id", str(place.id), "--lat", str(place.latitude), "--lon", str(place.longitude)]
        for place in _places_with_coordinates(db)
    ]


# Bounding box around a point, wide enough to catch airborne traffic
# serving a destination's airport(s) without a real per-airport
# bounding-box lookup this project doesn't have (~50km at mid-latitudes).
_OPENSKY_BBOX_DEGREES = 0.5


def build_argv_opensky(db: Session) -> list[list[str]]:
    half = _OPENSKY_BBOX_DEGREES / 2
    argv = []

    for place in _places_with_coordinates(db):
        # _places_with_coordinates already filtered these to non-null at
        # the SQL level; narrowed again here for the arithmetic below.
        assert place.latitude is not None
        assert place.longitude is not None

        argv.append(
            [
                "--place-id",
                str(place.id),
                "--lamin",
                str(place.latitude - half),
                "--lamax",
                str(place.latitude + half),
                "--lomin",
                str(place.longitude - half),
                "--lomax",
                str(place.longitude + half),
            ]
        )

    return argv


def build_argv_gdacs(db: Session) -> list[list[str]]:
    return [
        ["--place-id", str(place.id), "--country", place.destination.country_code]
        for place in _curated_places(db)
        if place.destination.country_code
    ]


# --- Wikipedia / YouTube / GDELT: derived from Place.name -------------------


def build_argv_wikipedia(db: Session) -> list[list[str]]:
    return [["--place-id", str(place.id), "--article", place.name] for place in _curated_places(db)]


def build_argv_youtube(db: Session) -> list[list[str]]:
    return [
        ["--place-id", str(place.id), "--query", f"{place.name} travel guide"]
        for place in _curated_places(db)
    ]


def build_argv_gdelt(db: Session) -> list[list[str]]:
    return [
        ["--place-id", str(place.id), "--query", f"{place.name} tourism", "--mode", "mentions"]
        for place in _curated_places(db)
    ]


# --- Events: Ticketmaster city search, city-level places only --------------


def build_argv_events(db: Session) -> list[list[str]]:
    return [
        [
            "--place-id",
            str(place.id),
            "--city",
            place.name,
            "--country-code",
            place.destination.country_code,
        ]
        for place in _curated_places(db)
        if place.place_type != "country" and place.destination.country_code
    ]


# --- KSH: Hungary-only, place name must be a supported tourism area --------


def build_argv_ksh(db: Session) -> list[list[str]]:
    argv = []
    for place in _curated_places(db):
        if place.destination.country_code != "HU":
            continue
        region = place.name.strip().lower()
        if region not in KSH_SUPPORTED_REGIONS:
            continue
        argv.append(["--place-id", str(place.id), "--region", region, "--backfill"])
    return argv


def build_argv_ksh_capacity(db: Session) -> list[list[str]]:
    place = next(
        (p for p in _country_places(db) if p.destination.country_code == "HU"),
        None,
    )
    if place is None:
        return []
    return [["--place-id", str(place.id), "--backfill"]]


# --- Eurostat: country-level places, every metric ---------------------------


_EUROSTAT_METRICS = ["nights", "arrivals", "occupancy_rate", "capacity", "economic", "population"]


def build_argv_eurostat(db: Session) -> list[list[str]]:
    argv = []
    for place in _country_places(db):
        country_code = place.destination.country_code
        if not country_code:
            continue
        # Eurostat uses EL for Greece, not ISO's GR.
        geo = eurostat_geo_code(country_code)
        for metric in _EUROSTAT_METRICS:
            argv.append(
                [
                    "--place-id",
                    str(place.id),
                    "--geo",
                    geo,
                    "--metric",
                    metric,
                    "--backfill",
                ]
            )
    return argv


# --- eurostat_regional: one run covers every NUTS region --------------------


def build_argv_once(db: Session) -> list[list[str]]:
    """Jobs that cover every place in one run (bulk loaders, forecasts)."""
    return [[]]


def build_argv_eurostat_regional(db: Session) -> list[list[str]]:
    """Annual regional indicators for all of Europe in one run, not per
    place; weekly because Eurostat revises and releases irregularly."""
    return [[]]


# Cadences are considered starting points, not measured constants -
# revisit once real ingestion run durations/rate limits are observed.
# Roughly: live/fast-changing sources every 30min-2h, daily-cadence
# content sources once a day, official-statistics sources monthly
# (their underlying data rarely changes more often than that).
_ONE_DAY_MINUTES = 24 * 60
_ONE_WEEK_MINUTES = 7 * _ONE_DAY_MINUTES
_ONE_MONTH_MINUTES = 30 * _ONE_DAY_MINUTES

SCHEDULED_ADAPTERS: list[ScheduledAdapter] = [
    ScheduledAdapter("weather", run_weather, build_argv_weather, interval_minutes=60),
    ScheduledAdapter("osm", run_osm, build_argv_osm, interval_minutes=_ONE_DAY_MINUTES),
    ScheduledAdapter("opensky", run_opensky, build_argv_opensky, interval_minutes=30),
    ScheduledAdapter("openaq", run_openaq, build_argv_openaq, interval_minutes=120),
    ScheduledAdapter("gdacs", run_gdacs, build_argv_gdacs, interval_minutes=30),
    ScheduledAdapter(
        "wikipedia", run_wikipedia, build_argv_wikipedia, interval_minutes=_ONE_DAY_MINUTES
    ),
    ScheduledAdapter("youtube", run_youtube, build_argv_youtube, interval_minutes=360),
    ScheduledAdapter("gdelt", run_gdelt, build_argv_gdelt, interval_minutes=360),
    ScheduledAdapter("events", run_events, build_argv_events, interval_minutes=_ONE_DAY_MINUTES),
    ScheduledAdapter("ksh", run_ksh, build_argv_ksh, interval_minutes=_ONE_MONTH_MINUTES),
    ScheduledAdapter(
        "ksh_capacity",
        run_ksh_capacity,
        build_argv_ksh_capacity,
        interval_minutes=_ONE_MONTH_MINUTES,
    ),
    ScheduledAdapter(
        "eurostat", run_eurostat, build_argv_eurostat, interval_minutes=_ONE_MONTH_MINUTES
    ),
    ScheduledAdapter(
        "eurostat_regional",
        run_eurostat_regional,
        build_argv_eurostat_regional,
        interval_minutes=_ONE_WEEK_MINUTES,
    ),
    # EU-wide official statistics for every place type, in one bulk run.
    ScheduledAdapter(
        "eurostat_bulk", run_eurostat_bulk, build_argv_once, interval_minutes=_ONE_WEEK_MINUTES
    ),
    # Monthly attention history: Wikipedia by language edition, GDELT
    # coverage and topics (the daily run downloads only the new day).
    ScheduledAdapter(
        "wikipedia_monthly",
        run_wikipedia_monthly,
        build_argv_once,
        interval_minutes=_ONE_WEEK_MINUTES,
    ),
    ScheduledAdapter(
        "gdelt_gkg", run_gdelt_gkg, build_argv_once, interval_minutes=_ONE_DAY_MINUTES
    ),
    # Inbound and economic context (research/gate3): monthly flights per
    # airport, and the Commission's tourism-sector business surveys. Both
    # publish once a month; a weekly run picks each release up within days.
    ScheduledAdapter(
        "eurocontrol", run_eurocontrol, build_argv_once, interval_minutes=_ONE_WEEK_MINUTES
    ),
    ScheduledAdapter(
        "ec_survey", run_ec_survey, build_argv_once, interval_minutes=_ONE_WEEK_MINUTES
    ),
    # Issues forecasts once a new official month lands; earlier live
    # forecasts are never overwritten.
    ScheduledAdapter(
        "forecasting", run_forecasting, build_argv_once, interval_minutes=_ONE_DAY_MINUTES
    ),
]
