"""Every EU27 location with official tourism statistics, as places.

- NUTS 2 regions ("region") and NUTS 3 areas ("area") that Eurostat
  publishes tourism indicators for, named and placed from the NUTS 2024
  boundaries already in PostGIS (ingestion.nuts).
- Eurostat Urban Audit cities ("city") with city tourism statistics
  (urb_ctour), placed from GISCO's city label points. A city that is
  already a hand-curated destination is linked (Place.urau_code), not
  duplicated.
- Hungary's KSH tourism areas that were not yet places.

Generated places carry Place.source_code, so re-running updates them.
They get official statistics (ingestion.eurostat_bulk) and the pressure
observatory; the Pulse and live signals stay on curated places.
"""
