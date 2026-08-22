from tourism_pulse_api.ingestion.openaq.client import build_latest_url, build_locations_url


def test_build_locations_url_includes_coordinates_and_radius() -> None:
    url = build_locations_url(latitude=47.4979, longitude=19.0402, radius_meters=25_000)

    assert "coordinates=47.4979%2C19.0402" in url
    assert "radius=25000" in url


def test_build_locations_url_uses_default_radius() -> None:
    url = build_locations_url(latitude=47.4979, longitude=19.0402)

    assert "radius=25000" in url


def test_build_latest_url_includes_location_id() -> None:
    url = build_latest_url(location_id=8901)

    assert url == "https://api.openaq.org/v3/locations/8901/latest"
