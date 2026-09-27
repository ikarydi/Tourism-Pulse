"""NUTS region boundaries from Eurostat GISCO - reference geography for
the tourism-pressure observatory.

Eurostat publishes regional tourism indicators by NUTS code; this adapter
loads the matching region polygons into PostGIS and assigns every place
its region code (NUTS 2 for destinations by point-in-polygon, NUTS 0 for
countries), so a place can be joined to its region's indicators. GISCO's
distribution endpoint is public and keyless.
"""
