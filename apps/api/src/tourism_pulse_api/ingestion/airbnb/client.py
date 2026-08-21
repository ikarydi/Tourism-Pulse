"""Airbnb has no public API - not even a restricted partner tier most
integrators can apply for.

`settings.airbnb_api_key` exists as a placeholder for a hypothetical
future licensed data source (e.g. a third-party provider such as AirDNA,
or an eventual Airbnb partner program), but is deliberately unused below:
there is no documented endpoint to call it against today, so pretending
otherwise would be worse than failing clearly.

No network call is ever attempted here.
"""

AIRBNB_SOURCE_NAME = "airbnb"


class SourceNotConfiguredError(RuntimeError):
    """Raised by every function in this module - Airbnb has no public API
    to configure credentials against."""


def fetch_listings(*, place_id: int, **_kwargs: object) -> str:
    raise SourceNotConfiguredError(
        "Airbnb has no public API. Real ingestion would require a "
        "licensed third-party data source or a future partner program "
        "(see this module's docstring) - not just an API key. "
        "Not implemented."
    )
