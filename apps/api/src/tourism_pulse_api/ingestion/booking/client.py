"""Booking.com has no accessible public read API.

Real access requires a signed Booking.com Partner Hub / Demand API
agreement - not just an API key, a commercial partnership this project
does not have. `settings.booking_api_key` exists as a placeholder for
that future agreement, but is deliberately unused below: even if a key
were configured, there is no documented public endpoint to call it
against, so pretending otherwise would be worse than failing clearly.

No network call is ever attempted here.
"""

BOOKING_SOURCE_NAME = "booking"


class SourceNotConfiguredError(RuntimeError):
    """Raised by every function in this module - Booking.com has no
    public API to configure credentials against."""


def fetch_availability(*, place_id: int, **_kwargs: object) -> str:
    raise SourceNotConfiguredError(
        "Booking.com has no public read API. Real ingestion requires a "
        "signed Partner Hub / Demand API agreement (see this module's "
        "docstring) - not just an API key. Not implemented."
    )
