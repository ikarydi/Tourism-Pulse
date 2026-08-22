"""Parser for OpenAQ v3's `/locations` (nearest-station search) and
`/locations/{id}/latest` (latest reading) responses.

https://docs.openaq.org/using-the-api/geospatial
https://docs.openaq.org/resources/latest

An empty `results` list from either endpoint is a valid result (no
monitoring station within range, or a station with no fresh reading
yet) - not an error, the same way OpenSky's empty airspace isn't one.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

OPENAQ_SOURCE_NAME = "openaq"
OPENAQ_API_BASE_URL = "https://api.openaq.org/v3"
PM25_PARAMETER_NAME = "pm25"


@dataclass(frozen=True)
class OpenaqLocation:
    """One monitoring station from a `/locations` geospatial search,
    with its PM2.5 sensor (if it has one) picked out."""

    id: int
    name: str
    pm25_sensor_id: int | None
    pm25_unit: str | None


@dataclass(frozen=True)
class AirQualityObservation:
    """A PM2.5 reading from one station's `/latest` response, combined
    with the station metadata `parse_openaq_locations` already found."""

    location_id: int
    location_name: str
    sensor_id: int
    pm25_value: float
    pm25_unit: str
    observed_at: datetime


def parse_openaq_locations(text: str) -> list[OpenaqLocation]:
    """Parse a `/locations` geospatial-search response.

    Raises `ValueError` if the response is not valid JSON or is missing
    an expected field - a malformed/unexpected response must not
    silently produce a fabricated observation. A location with no PM2.5
    sensor is still included (pm25_sensor_id=None) rather than dropped,
    so callers can see it was considered and skipped.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAQ response is not valid JSON: {exc}") from exc

    try:
        locations = []
        for entry in payload.get("results", []):
            pm25_sensor_id: int | None = None
            pm25_unit: str | None = None

            for sensor in entry.get("sensors", []):
                if sensor["parameter"]["name"].strip().lower() == PM25_PARAMETER_NAME:
                    pm25_sensor_id = int(sensor["id"])
                    pm25_unit = sensor["parameter"]["units"]
                    break

            locations.append(
                OpenaqLocation(
                    id=int(entry["id"]),
                    name=entry["name"],
                    pm25_sensor_id=pm25_sensor_id,
                    pm25_unit=pm25_unit,
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Unexpected OpenAQ locations response shape: {exc}") from exc

    return locations


def parse_openaq_latest(
    text: str,
    *,
    location: OpenaqLocation,
) -> AirQualityObservation | None:
    """Parse a `/locations/{id}/latest` response, picking out the reading
    for `location`'s PM2.5 sensor.

    Returns `None` if `location` has no PM2.5 sensor, or that sensor has
    no reading in the response - a station temporarily without a fresh
    reading is a valid result, not an error.

    Raises `ValueError` if the response is not valid JSON or is missing
    an expected field once a matching reading is found.
    """
    if location.pm25_sensor_id is None or location.pm25_unit is None:
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAQ response is not valid JSON: {exc}") from exc

    try:
        for entry in payload.get("results", []):
            if int(entry["sensorsId"]) != location.pm25_sensor_id:
                continue

            value = float(entry["value"])
            observed_at = datetime.fromisoformat(entry["datetime"]["utc"])
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=UTC)

            if value < 0:
                raise ValueError(f"OpenAQ reported a negative PM2.5 value: {value}")

            return AirQualityObservation(
                location_id=location.id,
                location_name=location.name,
                sensor_id=location.pm25_sensor_id,
                pm25_value=value,
                pm25_unit=location.pm25_unit,
                observed_at=observed_at,
            )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Unexpected OpenAQ latest response shape: {exc}") from exc

    return None
