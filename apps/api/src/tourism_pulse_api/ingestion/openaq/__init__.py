"""OpenAQ air-quality ingestion - fills the spec's explicitly-unimplemented
Environment source category (weather, air quality, climate - section
11.2) alongside the existing weather adapter.

OpenAQ v3 requires a free registered API key (`X-API-Key` header, see
https://docs.openaq.org/using-the-api/api-key) - unlike weather/OSM/
GDACS/Wikipedia, but the same as Ticketmaster/YouTube/OpenSky's
higher-quota tier. Never hardcoded, passed in explicitly by the caller
(see settings.openaq_api_key).

Two real HTTP calls per run, unlike every other adapter's one:
1. GET /v3/locations?coordinates=<lat>,<lon>&radius=<m> - find the
   nearest monitoring station (within 25km, OpenAQ's max radius) that
   has a PM2.5 sensor, and that sensor's id/unit.
2. GET /v3/locations/{id}/latest - that station's latest reading per
   sensor id.
Kept as two client.py functions rather than one combined call because
OpenAQ's `latest` endpoint doesn't itself say *which pollutant* a
reading is for (only a `sensorsId`) - the parameter/unit has to come
from step 1's sensor list.
"""
