"""Summarise one GDELT daily Global Knowledge Graph file per curated place.

Each daily file (data.gdeltproject.org/gkg/YYYYMMDD.gkg.csv.zip, 20-35 MB)
lists article records with THEMES, LOCATIONS and TONE. For every place this
keeps, per day:

- mentions: articles whose locations include the place (any theme),
- tourism: those that also carry a tourism theme,
- the tone of each, and
- how many tourism articles touch each topic group below.

The day's totals (all articles, all tourism articles and their topics)
are kept too, so the monthly figures can be shares and topic lifts.

GDELT's 1.0 daily files are dominated by English-language sources, so
these figures describe international English-language coverage.
"""

import math
import unicodedata
from dataclasses import dataclass

# The same tourism themes the nowcast research used (research/nowcast/gkg.py).
TOURISM_THEMES = frozenset(
    {"TOURISM", "WB_825_TOURISM", "TAX_FNCACT_TOURIST", "TAX_FNCACT_TOURISTS"}
)

# Topic groups for tourism coverage. A theme matches a group if it equals
# one of the names, or starts with one of the prefixes. Chosen from the
# themes that co-occur with tourism in real daily files; deliberately
# narrow (e.g. GENERAL_HEALTH and MANMADE_DISASTER_IMPLIED are too broad).
TOPICS: dict[str, tuple[frozenset[str], tuple[str, ...]]] = {
    "protest": (frozenset({"PROTEST"}), ()),
    "strike": (frozenset({"STRIKE"}), ()),
    "security": (
        frozenset({"TERROR", "KILL", "SOC_GENERALCRIME", "ARREST", "ARMEDCONFLICT"}),
        ("CRIME_",),
    ),
    "disaster": (frozenset({"DISASTER_FIRE"}), ("NATURAL_DISASTER",)),
    "climate": (
        frozenset(
            {
                "ENV_CLIMATECHANGE",
                "UNGP_CLIMATE_CHANGE_ACTION",
                "WB_567_CLIMATE_CHANGE",
                "WB_1773_CLIMATE_CHANGE_IMPACTS",
            }
        ),
        (),
    ),
    "health": (
        frozenset({"HEALTH_PANDEMIC", "WB_2167_PANDEMICS", "WB_1406_DISEASES"}),
        ("TAX_DISEASE",),
    ),
    "prices": (
        frozenset(
            {
                "TAX_ECON_PRICE",
                "ECON_INFLATION",
                "WB_442_INFLATION",
                "ECON_COST_OF_LIVING",
                "FUELPRICES",
            }
        ),
        (),
    ),
    "housing": (
        frozenset(
            {
                "ECON_HOUSING_PRICES",
                "WB_904_HOUSING_MARKETS",
                "WB_817_LAND_AND_HOUSING",
                "WB_612_HOUSING_FINANCE",
                "WB_2186_SOCIAL_HOUSING",
            }
        ),
        (),
    ),
    "air_travel": (
        frozenset(
            {
                "WB_1804_AIRPORTS",
                "SOC_POINTSOFINTEREST_AIRPORT",
                "SOC_POINTSOFINTEREST_AIRPORTS",
                "WB_165_AIR_TRANSPORT",
                "AVIATION_INCIDENT",
            }
        ),
        (),
    ),
    "heritage": (frozenset({"WB_1765_CULTURE_HERITAGE_AND_SUSTAINABLE_TOURISM"}), ()),
}

# Eurostat geo code -> FIPS 10-4 country code used in GKG LOCATIONS.
FIPS: dict[str, str] = {
    "AT": "AU", "BE": "BE", "BG": "BU", "CY": "CY", "CZ": "EZ", "DE": "GM",
    "DK": "DA", "EE": "EN", "EL": "GR", "ES": "SP", "FI": "FI", "FR": "FR",
    "HR": "HR", "HU": "HU", "IE": "EI", "IT": "IT", "LT": "LH", "LU": "LU",
    "LV": "LG", "MT": "MT", "NL": "NL", "PL": "PL", "PT": "PO", "RO": "RO",
    "SE": "SW", "SI": "SI", "SK": "LO",
}  # fmt: skip

# GKG location types: 3 = US city, 4 = world city. Countries (1) and
# first-order divisions (2, 5) are too coarse to place in a city.
CITY_LOCATION_TYPES = frozenset({"3", "4"})
DEFAULT_RADIUS_KM = 15.0

# Hungarian tourism areas are several towns each; matched by town name as
# in the nowcast research (research/nowcast/gkg_regional.py). Budapest is
# matched by its first-order division code.
BUDAPEST_ADM1 = "HU05"
KSH_AREA_TOWNS: dict[str, frozenset[str]] = {
    "Balaton": frozenset({"siofok", "keszthely", "heviz", "tihany", "zamardi", "fonyod"}),
    "Greater Budapest": frozenset({"szentendre", "visegrad", "godollo", "vac"}),
    "Bük and Sárvár": frozenset({"buk", "bukfurdo", "sarvar"}),
    "Debrecen": frozenset({"debrecen", "hajduszoboszlo"}),
    "Győr and Pannonhalma": frozenset({"gyor", "pannonhalma"}),
    "Gyula": frozenset({"gyula"}),
    "Eger": frozenset({"eger", "egerszalok"}),
    "Pécs": frozenset({"pecs"}),
    "Sopron": frozenset({"sopron"}),
    "Szeged": frozenset({"szeged"}),
    "Tokaj and Nyíregyháza": frozenset({"tokaj", "nyiregyhaza"}),
}
# Places also matched when a Hungarian location name starts with these.
KSH_AREA_PREFIXES: dict[str, tuple[str, ...]] = {"Balaton": ("balaton", "lake balaton")}


@dataclass(frozen=True)
class Target:
    """A place to count coverage for. Exactly one way of matching applies:
    a country code, a Hungarian town list, Budapest's division, or a point
    with a radius."""

    place_id: int
    fips: str
    country: bool = False
    towns: frozenset[str] = frozenset()
    prefixes: tuple[str, ...] = ()
    adm1: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float = DEFAULT_RADIUS_KM


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip()


def topics_of(themes: set[str]) -> list[str]:
    found = []
    for topic, (names, prefixes) in TOPICS.items():
        if not names.isdisjoint(themes) or any(
            theme.startswith(prefix) for prefix in prefixes for theme in themes
        ):
            found.append(topic)
    return found


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Equirectangular approximation; exact enough within a few dozen km.
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371.0 * math.hypot(x, y)


class Matcher:
    """Finds the targets a record's LOCATIONS field mentions."""

    def __init__(self, targets: list[Target]):
        self.by_country: dict[str, list[int]] = {}
        self.by_adm1: dict[str, list[int]] = {}
        self.by_town: dict[str, list[int]] = {}
        self.by_prefix: list[tuple[str, int]] = []
        self.points_by_fips: dict[str, list[Target]] = {}
        for target in targets:
            if target.country:
                self.by_country.setdefault(target.fips, []).append(target.place_id)
            elif target.adm1:
                self.by_adm1.setdefault(target.adm1, []).append(target.place_id)
            elif target.towns or target.prefixes:
                for town in target.towns:
                    self.by_town.setdefault(town, []).append(target.place_id)
                self.by_prefix.extend((prefix, target.place_id) for prefix in target.prefixes)
            elif target.latitude is not None and target.longitude is not None:
                self.points_by_fips.setdefault(target.fips, []).append(target)

    def match(self, locations: str) -> set[int]:
        found: set[int] = set()
        for location in locations.split(";"):
            parts = location.split("#")
            if len(parts) < 6:
                continue
            kind, name, fips, adm1 = parts[0], parts[1], parts[2], parts[3]
            found.update(self.by_country.get(fips, ()))
            if adm1 in self.by_adm1:
                found.update(self.by_adm1[adm1])
            if fips == "HU" and (self.by_town or self.by_prefix):
                first = fold(name.split(",")[0])
                found.update(self.by_town.get(first, ()))
                found.update(
                    place_id for prefix, place_id in self.by_prefix if first.startswith(prefix)
                )
            points = self.points_by_fips.get(fips)
            if points and kind in CITY_LOCATION_TYPES:
                try:
                    lat, lon = float(parts[4]), float(parts[5])
                except ValueError:
                    continue
                for target in points:
                    assert target.latitude is not None and target.longitude is not None
                    distance = _distance_km(lat, lon, target.latitude, target.longitude)
                    if distance <= target.radius_km:
                        found.add(target.place_id)
        return found


def empty_counts() -> dict:
    return {"mentions": 0, "mention_tone": 0.0, "tourism": 0, "tourism_tone": 0.0, "topics": {}}


def summarise_day(text: str, targets: list[Target]) -> dict:
    """Per-place counts for one daily file (see module docstring).

    Tones are stored as article-weighted sums; divide by the matching
    count to get a mean."""
    matcher = Matcher(targets)
    corpus = 0
    tourism_total = 0
    topic_totals: dict[str, int] = {}
    places: dict[int, dict] = {}

    for line in text.splitlines()[1:]:  # first line is the header
        fields = line.split("\t", 9)
        if len(fields) < 8 or not fields[1].isdigit():
            continue
        numarts = int(fields[1])
        corpus += numarts

        themes_field = fields[3]
        themes = set(themes_field.split(";")) if "TOURIS" in themes_field else set()
        is_tourism = not TOURISM_THEMES.isdisjoint(themes)
        topics: list[str] = []
        if is_tourism:
            tourism_total += numarts
            topics = topics_of(themes)
            for topic in topics:
                topic_totals[topic] = topic_totals.get(topic, 0) + numarts

        if not fields[4]:
            continue
        matched = matcher.match(fields[4])
        if not matched:
            continue
        tone = float(fields[7].split(",")[0]) if fields[7] else 0.0
        for place_id in matched:
            counts = places.setdefault(place_id, empty_counts())
            counts["mentions"] += numarts
            counts["mention_tone"] += tone * numarts
            if is_tourism:
                counts["tourism"] += numarts
                counts["tourism_tone"] += tone * numarts
                for topic in topics:
                    counts["topics"][topic] = counts["topics"].get(topic, 0) + numarts

    return {
        "corpus": corpus,
        "tourism": tourism_total,
        "topics": topic_totals,
        "places": {str(place_id): counts for place_id, counts in places.items()},
    }
