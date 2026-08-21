"""Airbnb listing/demand ingestion - SCAFFOLD ONLY, not a live adapter.

Airbnb has no public API at all - not even a restricted partner one for
most integrators. Per spec section 50 rule 4/7 ("never hardcode external
source data into production logic", "every external source requires an
adapter"), scraping is not an acceptable substitute for a real adapter -
it is fragile, ToS-violating, and easily blockable, so it is deliberately
not attempted here.

This package exists so that, if real access ever becomes available (e.g.
a licensed third-party data provider such as AirDNA, or a future Airbnb
partner program), wiring it in is a `client.py` diff against an
already-correct package shape (mirroring every other `ingestion/<source>/`
package: client/parser/service/__main__), not a rewrite. See `client.py`
for the exact failure contract in the meantime.
"""
