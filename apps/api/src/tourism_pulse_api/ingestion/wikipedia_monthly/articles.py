"""Which Wikipedia articles stand for a place."""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = "tourism-pulse-ingestion/1.0"

# Curated destination names whose plain title is ambiguous or means
# something else (the destination "Luxembourg" is the city, not the country).
DESTINATION_TITLES: dict[str, str] = {
    "Faro": "Faro, Portugal",
    "Luxembourg": "Luxembourg City",
}

# KSH tourism areas: the towns' articles, per language.
KSH_AREA_ARTICLES: dict[str, dict[str, list[str]]] = {
    "Budapest": {"hu": ["Budapest"], "en": ["Budapest"], "de": ["Budapest"]},
    "Balaton": {"hu": ["Balaton"], "en": ["Lake_Balaton"], "de": ["Balaton"]},
    "Greater Budapest": {"hu": ["Szentendre"], "en": ["Szentendre"], "de": ["Szentendre"]},
    "Bük and Sárvár": {"hu": ["Bük", "Sárvár"], "en": ["Bük", "Sárvár"], "de": ["Bük", "Sárvár"]},
    "Debrecen": {
        "hu": ["Debrecen", "Hajdúszoboszló"],
        "en": ["Debrecen", "Hajdúszoboszló"],
        "de": ["Debrecen", "Hajdúszoboszló"],
    },
    "Győr and Pannonhalma": {
        "hu": ["Győr", "Pannonhalma"],
        "en": ["Győr", "Pannonhalma"],
        "de": ["Győr", "Pannonhalma"],
    },
    "Gyula": {"hu": ["Gyula_(Magyarország)"], "en": ["Gyula,_Hungary"], "de": ["Gyula"]},
    "Eger": {"hu": ["Eger"], "en": ["Eger"], "de": ["Eger_(Ungarn)"]},
    "Pécs": {"hu": ["Pécs"], "en": ["Pécs"], "de": ["Pécs"]},
    "Sopron": {"hu": ["Sopron"], "en": ["Sopron"], "de": ["Sopron"]},
    "Szeged": {"hu": ["Szeged"], "en": ["Szeged"], "de": ["Szeged"]},
    "Tokaj and Nyíregyháza": {
        "hu": ["Tokaj", "Nyíregyháza"],
        "en": ["Tokaj", "Nyíregyháza"],
        "de": ["Tokaj", "Nyíregyháza"],
    },
}


@dataclass(frozen=True)
class Article:
    language: str
    title: str


def resolve_en_titles(names: list[str]) -> dict[str, tuple[str, str | None] | None]:
    """name -> (English title, German title) after redirects; None when the
    name is missing or a disambiguation page."""
    out: dict[str, tuple[str, str | None] | None] = {}
    for start in range(0, len(names), 50):
        batch = names[start : start + 50]
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "redirects": 1,
                "prop": "pageprops|langlinks",
                "lllang": "de",
                "lllimit": "max",
                "titles": "|".join(batch),
            }
        )
        request = urllib.request.Request(
            f"https://en.wikipedia.org/w/api.php?{query}", headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            result = json.load(response)["query"]
        normalized = {item["from"]: item["to"] for item in result.get("normalized", [])}
        redirects = {item["from"]: item["to"] for item in result.get("redirects", [])}
        pages = {page["title"]: page for page in result.get("pages", [])}
        for name in batch:
            title = normalized.get(name, name)
            title = redirects.get(title, title)
            page = pages.get(title, {})
            if page.get("missing") or "disambiguation" in page.get("pageprops", {}):
                out[name] = None
                continue
            links = page.get("langlinks") or []
            out[name] = (title, links[0]["title"] if links else None)
    return out
