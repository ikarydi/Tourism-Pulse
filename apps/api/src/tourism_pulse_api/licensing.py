"""Which data sources may appear in something that is sold.

Ingesting a source for research and selling output built on it are
different rights. Every source the adapters write under is listed here
with what its publisher's terms say about commercial reuse, the page
that was read, and the date it was read. Paid output (briefs.build) only
draws on sources marked ALLOWED; anything else is withheld and named.

A source missing from this table is treated as UNVERIFIED, so a new
adapter cannot reach paid output until someone has read its terms.
This is a reading of published terms, not legal advice.
"""

from dataclasses import dataclass

ALLOWED = "allowed"
LICENCE_REQUIRED = "licence_required"
UNVERIFIED = "unverified"


@dataclass(frozen=True)
class SourceLicence:
    name: str
    title: str
    commercial_use: str
    licence: str
    attribution: str | None
    terms_url: str | None
    checked_on: str | None


def _source(name, title, commercial_use, licence, attribution=None, terms_url=None, checked=None):
    return SourceLicence(name, title, commercial_use, licence, attribution, terms_url, checked)


_CHECKED = "2026-11-12"

LICENCES: dict[str, SourceLicence] = {
    row.name: row
    for row in (
        _source(
            "eurostat",
            "Eurostat",
            ALLOWED,
            "Reuse authorised with acknowledgement (Commission reuse policy)",
            "Source: Eurostat. Figures are derived by Tourism Pulse and are not Eurostat's own.",
            "https://ec.europa.eu/eurostat/help/copyright-notice",
            _CHECKED,
        ),
        _source(
            "gisco",
            "Eurostat GISCO (NUTS boundaries)",
            ALLOWED,
            "Reuse authorised with acknowledgement (Commission reuse policy)",
            "Administrative boundaries: © EuroGeographics, source: European Commission - "
            "Eurostat/GISCO.",
            "https://ec.europa.eu/eurostat/help/copyright-notice",
            _CHECKED,
        ),
        _source(
            "ksh",
            "Hungarian Central Statistical Office (KSH)",
            ALLOWED,
            "CC BY 4.0 for published content; custom extracts are non-commercial",
            "Source: Hungarian Central Statistical Office (KSH), CC BY 4.0.",
            "https://www.ksh.hu/copyright",
            _CHECKED,
        ),
        _source(
            "gdelt",
            "GDELT Project",
            ALLOWED,
            "Unrestricted use, including commercial, with citation and link",
            "News data: the GDELT Project (https://www.gdeltproject.org/).",
            "https://www.gdeltproject.org/about.html",
            _CHECKED,
        ),
        _source(
            "wikipedia",
            "Wikimedia pageviews",
            ALLOWED,
            "CC0 (all Wikimedia Analytics datasets)",
            "Page views: Wikimedia Foundation, CC0.",
            "https://dumps.wikimedia.org/other/pageviews/readme.html",
            _CHECKED,
        ),
        _source(
            "opensky",
            "OpenSky Network",
            LICENCE_REQUIRED,
            "Any for-profit use needs written permission and a licence",
            None,
            "https://opensky-network.org/about/terms-of-use",
            _CHECKED,
        ),
        _source(
            "eurocontrol",
            "EUROCONTROL",
            LICENCE_REQUIRED,
            "Reuse only where not for financial gain",
            None,
            "https://ansperformance.eu/about/disclaimer/",
            _CHECKED,
        ),
        _source(
            "open-meteo",
            "Open-Meteo",
            LICENCE_REQUIRED,
            "Free API is non-commercial; a paid plan grants a commercial licence",
            None,
            "https://open-meteo.com/en/terms",
            _CHECKED,
        ),
        _source(
            "ticketmaster",
            "Ticketmaster Discovery API",
            LICENCE_REQUIRED,
            "Terms bar deriving revenue from the API",
            None,
            "https://developer.ticketmaster.com/support/terms-of-use/",
            _CHECKED,
        ),
        _source(
            "youtube",
            "YouTube Data API",
            LICENCE_REQUIRED,
            "No derived metrics, 30-day storage limit, no sale without written approval",
            None,
            "https://developers.google.com/youtube/terms/developer-policies",
            _CHECKED,
        ),
        _source(
            "reddit",
            "Reddit Data API",
            LICENCE_REQUIRED,
            "Free tier is non-commercial; commercial use needs an agreement (not re-read)",
        ),
        _source(
            "openaq",
            "OpenAQ",
            UNVERIFIED,
            "Each upstream provider's terms apply",
            None,
            "https://docs.openaq.org/about/terms",
            _CHECKED,
        ),
        _source("bluesky", "Bluesky", UNVERIFIED, "Terms not yet read for commercial use"),
        _source("osm", "OpenStreetMap", UNVERIFIED, "ODbL; share-alike terms not yet assessed"),
        _source("gdacs", "GDACS", UNVERIFIED, "Terms not yet read for commercial use"),
    )
}


def licence_for(source: str) -> SourceLicence:
    name = source.strip().lower()
    known = LICENCES.get(name)
    if known is not None:
        return known
    return SourceLicence(name, name, UNVERIFIED, "Terms not yet read", None, None, None)


def cleared(source: str) -> bool:
    return licence_for(source).commercial_use == ALLOWED


def not_cleared(sources: list[str] | set[str]) -> list[str]:
    """The sources in `sources` that may not appear in paid output."""
    return sorted({source.strip().lower() for source in sources if not cleared(source)})
