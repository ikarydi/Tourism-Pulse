"""Official tourism time series for every EU27 location, in bulk.

Loads Eurostat series for all countries, NUTS 2 regions, NUTS 3 areas
and Urban Audit cities at once (the per-place eurostat adapter fetches
one country at a time and only national series):

- countries: monthly nights and arrivals since 2014
- regions / areas: monthly nights (from 2020, where published), annual
  nights, bed places and platform-booked nights
- cities: annual nights, bed places, nights per resident, domestic and
  foreign nights, museum visitors
- countries / regions / areas: population (PlaceDemographics)

Each Eurostat code maps to exactly one place type (a country's national
code never lands on a destination that shares it, a NUTS 2 code only on
the region place), so region figures never overwrite a curated
destination's own series. Values are validated in bulk (finite, within
the data-quality range bounds) instead of through the per-row gate, and
every raw payload is archived for lineage.
"""
