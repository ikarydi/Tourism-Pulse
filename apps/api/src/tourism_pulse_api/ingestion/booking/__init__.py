"""Booking.com accommodation-demand ingestion - SCAFFOLD ONLY, not a live
adapter.

Booking.com has no open public read API. Real access requires a signed
Booking.com Partner Hub / Demand API agreement this project does not have.
Per spec section 50 rule 4/7 ("never hardcode external source data into
production logic", "every external source requires an adapter"),
scraping is not an acceptable substitute for a real adapter - it is
fragile, ToS-violating, and easily blockable, so it is deliberately not
attempted here.

This package exists so that, once real partner credentials exist, wiring
them in is a `client.py` diff against an already-correct package shape
(mirroring every other `ingestion/<source>/` package: client/parser/
service/__main__), not a rewrite. See `client.py` for the exact failure
contract in the meantime.
"""
