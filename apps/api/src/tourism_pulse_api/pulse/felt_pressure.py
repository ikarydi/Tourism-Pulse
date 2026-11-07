"""Felt pressure: the share of social posts about a place that complain
about crowding, prices or short-term lets.

Deterministic by design (the Pulse rule: no ML or LLM in scores). A post
counts when its text contains any term below at the start of a word,
ignoring case and Greek accents: the stem "crowd" matches "crowded" and
"crowds", and "overcrowding" matches its own stem "overcrowd". The lexicon is fixed by the Gate 4
pre-registration (research/gate4/PREREGISTRATION.md, Part 2): change it
only with a new pre-registration, never to make a result look better.

Languages: English, Greek, Hungarian and German, the languages of the
pilot places (Crete, Budapest, Balaton) and their largest source market.
"""

import re
import unicodedata

LEXICON_VERSION = "2026-11-07"

# Stems match the start of a word ("overtouris" matches "overtourism" and
# "overtourist"); whole words are listed in full.
FELT_PRESSURE_TERMS: dict[str, tuple[str, ...]] = {
    "en": (
        "overtouris", "too many tourists", "crowd", "overcrowd", "packed",
        "queue", "tourist trap", "rip-off", "ripoff", "overpriced",
        "expensive", "airbnb", "short-term rental", "short term rental",
        "rent", "housing crisis", "noise", "litter", "traffic jam",
    ),
    "el": (
        "υπερτουρισμ", "πολλοί τουρίστες", "συνωστισμ", "κοσμοσυρροή",
        "ουρά", "ουρές", "ακριβ", "airbnb", "βραχυχρόνι", "ενοίκι",
        "στεγαστικ", "θόρυβ", "σκουπίδ", "κίνηση",
    ),
    "hu": (
        "túlturizmus", "túl sok turista", "tömeg", "zsúfolt", "sorban áll",
        "drága", "lehúzás", "airbnb", "rövid távú", "albérlet", "lakhatás",
        "zaj", "szemét", "dugó",
    ),
    "de": (
        "übertourismus", "overtourism", "zu viele touristen", "überfüllt",
        "menschenmassen", "warteschlange", "touristenfalle", "abzocke",
        "überteuert", "teuer", "airbnb", "ferienwohnung", "mieten",
        "wohnungsnot", "lärm", "müll", "stau",
    ),
}  # fmt: skip


def _fold(text: str) -> str:
    """Lower-case and strip Greek accents so "Ακριβό" matches "ακριβ"."""
    decomposed = unicodedata.normalize("NFD", text.casefold())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def _compile() -> re.Pattern[str]:
    terms = sorted({_fold(t) for terms in FELT_PRESSURE_TERMS.values() for t in terms})
    alternatives = "|".join(re.escape(t) for t in terms)
    # A term must start a word: "rent" matches "rents" and "rental" but not
    # "parent" or "current".
    return re.compile(rf"(?<!\w)(?:{alternatives})")


_PATTERN = _compile()


def mentions_felt_pressure(text: str) -> bool:
    return _PATTERN.search(_fold(text)) is not None


def felt_pressure_share(texts: list[str]) -> float | None:
    """Share of `texts` (0-1) that mention felt pressure; None for no texts."""
    if not texts:
        return None
    return sum(mentions_felt_pressure(t) for t in texts) / len(texts)
