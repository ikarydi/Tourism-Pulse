"""Which Wikipedia articles stand for a place."""

import json
import time
import urllib.error
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


# Language editions read as source markets: the EU's big travel markets and
# the largest long-haul ones. A place's own language is added to these.
MARKET_LANGUAGES: tuple[str, ...] = (
    "en", "de", "fr", "it", "es", "nl", "pl", "pt", "sv", "da", "fi", "cs",
    "hu", "ro", "el", "ru", "uk", "tr", "ar", "he", "zh", "ja", "ko",
)  # fmt: skip

# Main Wikipedia language of each EU country (ISO code).
LOCAL_LANGUAGES: dict[str, str] = {
    "AT": "de", "BE": "nl", "BG": "bg", "CY": "el", "CZ": "cs", "DE": "de",
    "DK": "da", "EE": "et", "ES": "es", "FI": "fi", "FR": "fr", "GR": "el",
    "HR": "hr", "HU": "hu", "IE": "en", "IT": "it", "LT": "lt", "LU": "lb",
    "LV": "lv", "MT": "mt", "NL": "nl", "PL": "pl", "PT": "pt", "RO": "ro",
    "SE": "sv", "SI": "sl", "SK": "sk",
}  # fmt: skip


def _api_get(params: dict) -> dict:
    """One MediaWiki API call, paced and retried on 429 (too many requests)."""
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"https://en.wikipedia.org/w/api.php?{query}", headers={"User-Agent": USER_AGENT}
    )
    for attempt in range(6):
        time.sleep(1.0)  # language links take many continued calls; keep them apart
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 5:
                raise
            time.sleep(2**attempt * 5)
    raise RuntimeError("unreachable")


def resolve_titles(names: list[str]) -> dict[str, dict[str, str] | None]:
    """name -> {language: title} for the English article (after redirects)
    and every language edition it links to; None when the name is missing
    or a disambiguation page."""
    out: dict[str, dict[str, str] | None] = {}
    for start in range(0, len(names), 20):
        batch = names[start : start + 20]
        pages, normalized, redirects = {}, {}, {}
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "redirects": 1,
            "prop": "pageprops|langlinks",
            "lllimit": "max",
            "titles": "|".join(batch),
        }
        # Language links come back in pages of up to 500; follow "continue".
        while True:
            body = _api_get(params)
            result = body["query"]
            normalized.update({item["from"]: item["to"] for item in result.get("normalized", [])})
            redirects.update({item["from"]: item["to"] for item in result.get("redirects", [])})
            for page in result.get("pages", []):
                known = pages.setdefault(page["title"], {**page, "langlinks": []})
                known["langlinks"].extend(page.get("langlinks") or [])
            if "continue" not in body:
                break
            params.update(body["continue"])
        for name in batch:
            title = normalized.get(name, name)
            title = redirects.get(title, title)
            page = pages.get(title, {})
            if page.get("missing") or "disambiguation" in page.get("pageprops", {}):
                out[name] = None
                continue
            titles = {link["lang"]: link["title"] for link in page.get("langlinks", [])}
            out[name] = {"en": title, **titles}
    return out
