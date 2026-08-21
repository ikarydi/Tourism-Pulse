"""No upsert function exists yet - there is nothing to upsert without a
real, verified payload shape (see parser.py) or a working fetch (see
client.py's `SourceNotConfiguredError`). Once real Booking.com access
exists, this module gains an `upsert_*_signal` function following the
same data-quality-gated pattern every other adapter's service.py already
uses (see e.g. ingestion.osm.service.upsert_poi_count_signal).
"""
