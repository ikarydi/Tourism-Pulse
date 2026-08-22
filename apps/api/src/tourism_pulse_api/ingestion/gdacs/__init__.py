"""GDACS (Global Disaster Alert and Coordination System) ingestion - the
first real data for a new `risk` dimension.

GDACS is a UN/European-Commission-affiliated multi-agency system
covering earthquakes, floods, tropical cyclones, volcanoes, wildfires
and droughts, free and keyless
(https://www.gdacs.org/gdacsapi/swagger/index.html). Unlike weather
(environment/comfort) or OSM (POI counts), a hazard alert genuinely
doesn't belong in any of the original 4 dimensions - none of them are
about hazard risk - which is why the Pulse engine was extended with a
`risk` dimension before this adapter was written (see
pulse.coefficients).
"""
