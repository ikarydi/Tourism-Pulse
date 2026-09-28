"""Tests for the scheduler's argv-builders - each turns the current
places/destinations tables into argv lists derived from Place/
Destination data, not a hardcoded per-place table. Uses a small,
purpose-built set of places rather than the real seeded dataset, so
these tests don't depend on what happens to be in the dev DB."""

import pytest
from tourism_pulse_api.db.models import Destination, Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.scheduler.jobs import (
    build_argv_eurostat,
    build_argv_events,
    build_argv_gdacs,
    build_argv_gdelt,
    build_argv_ksh,
    build_argv_ksh_capacity,
    build_argv_openaq,
    build_argv_opensky,
    build_argv_osm,
    build_argv_weather,
    build_argv_wikipedia,
    build_argv_youtube,
)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def hungary(db_session) -> Destination:
    destination = Destination(country_code="HU", name="Scheduler Test Hungary")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)
    return destination


@pytest.fixture()
def budapest(db_session, hungary) -> Place:
    place = Place(
        destination_id=hungary.id,
        name="Budapest",
        place_type="destination",
        latitude=47.4979,
        longitude=19.0402,
    )
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


@pytest.fixture()
def hungary_country_place(db_session, hungary) -> Place:
    place = Place(destination_id=hungary.id, name="Hungary", place_type="country")
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


@pytest.fixture()
def greece(db_session) -> Destination:
    destination = Destination(country_code="GR", name="Scheduler Test Greece")
    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)
    return destination


@pytest.fixture()
def greece_country_place(db_session, greece) -> Place:
    place = Place(destination_id=greece.id, name="Greece", place_type="country")
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


@pytest.fixture()
def place_with_no_coordinates(db_session, hungary) -> Place:
    place = Place(destination_id=hungary.id, name="Somewhere", place_type="destination")
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place


# --- lat/lon-driven adapters --------------------------------------------------


@pytest.mark.parametrize(
    "build_argv", [build_argv_weather, build_argv_osm, build_argv_openaq]
)
def test_lat_lon_adapters_include_places_with_coordinates(
    db_session, budapest, build_argv
) -> None:
    argv_list = build_argv(db_session)

    assert any(str(budapest.id) in argv for argv in argv_list)


@pytest.mark.parametrize(
    "build_argv", [build_argv_weather, build_argv_osm, build_argv_openaq]
)
def test_lat_lon_adapters_skip_places_without_coordinates(
    db_session, place_with_no_coordinates, build_argv
) -> None:
    argv_list = build_argv(db_session)

    assert not any(str(place_with_no_coordinates.id) in argv for argv in argv_list)


def test_opensky_builds_a_bounding_box_around_the_place(db_session, budapest) -> None:
    argv_list = build_argv_opensky(db_session)

    matching = next(argv for argv in argv_list if str(budapest.id) in argv)
    assert "--lamin" in matching
    assert "--lamax" in matching
    assert "--lomin" in matching
    assert "--lomax" in matching

    lamin = float(matching[matching.index("--lamin") + 1])
    lamax = float(matching[matching.index("--lamax") + 1])
    assert lamin < budapest.latitude < lamax


# --- country-code-driven adapters --------------------------------------------


def test_gdacs_uses_the_place_destination_country_code(db_session, budapest) -> None:
    argv_list = build_argv_gdacs(db_session)

    matching = next(argv for argv in argv_list if str(budapest.id) in argv)
    assert "--country" in matching
    assert matching[matching.index("--country") + 1] == "HU"


# --- Place.name-derived adapters ---------------------------------------------


def test_wikipedia_uses_the_place_name_as_the_article(db_session, budapest) -> None:
    argv_list = build_argv_wikipedia(db_session)

    matching = next(argv for argv in argv_list if str(budapest.id) in argv)
    assert matching[matching.index("--article") + 1] == "Budapest"


def test_youtube_uses_the_place_name_in_the_query(db_session, budapest) -> None:
    argv_list = build_argv_youtube(db_session)

    matching = next(argv for argv in argv_list if str(budapest.id) in argv)
    assert "Budapest" in matching[matching.index("--query") + 1]


def test_gdelt_uses_the_place_name_in_the_query_and_mentions_mode(db_session, budapest) -> None:
    argv_list = build_argv_gdelt(db_session)

    matching = next(argv for argv in argv_list if str(budapest.id) in argv)
    assert "Budapest" in matching[matching.index("--query") + 1]
    assert matching[matching.index("--mode") + 1] == "mentions"


# --- events: city-level places only ------------------------------------------


def test_events_includes_city_level_places(db_session, budapest) -> None:
    argv_list = build_argv_events(db_session)

    assert any(str(budapest.id) in argv for argv in argv_list)


def test_events_excludes_country_level_places(db_session, hungary_country_place) -> None:
    argv_list = build_argv_events(db_session)

    assert not any(str(hungary_country_place.id) in argv for argv in argv_list)


# --- KSH: name must match a supported tourism area --------------------------


def test_ksh_includes_a_place_whose_name_matches_a_supported_region(
    db_session, budapest
) -> None:
    argv_list = build_argv_ksh(db_session)

    matching = next(argv for argv in argv_list if str(budapest.id) in argv)
    assert matching[matching.index("--region") + 1] == "budapest"


def test_ksh_skips_a_place_whose_name_is_not_a_supported_region(
    db_session, place_with_no_coordinates
) -> None:
    argv_list = build_argv_ksh(db_session)

    assert not any(str(place_with_no_coordinates.id) in argv for argv in argv_list)


def test_ksh_capacity_picks_at_most_one_job(db_session, hungary_country_place) -> None:
    # Other test files' fixtures may also leave behind a "country"-typed
    # HU place in the shared test DB (no per-test rollback in this
    # codebase's test setup - see tests/conftest.py), so this can't
    # assert exactly which place wins, only that the "one national
    # series" contract (at most one job) holds regardless of how many
    # HU country places exist.
    argv_list = build_argv_ksh_capacity(db_session)

    assert len(argv_list) <= 1


# --- Eurostat: country-level places, every metric ----------------------------


def test_eurostat_uses_the_destination_country_code_as_geo(
    db_session, hungary_country_place
) -> None:
    argv_list = build_argv_eurostat(db_session)

    matching = next(argv for argv in argv_list if str(hungary_country_place.id) in argv)
    assert matching[matching.index("--geo") + 1] == "HU"


def test_eurostat_remaps_greece_to_eurostats_own_geo_code(
    db_session, greece_country_place
) -> None:
    # Regression: Eurostat's own geo code for Greece is "EL", not the ISO
    # 3166-1 "GR" stored on Destination.country_code - passing "GR"
    # straight through silently returns zero rows every scheduled run.
    argv_list = build_argv_eurostat(db_session)

    matching_jobs = [argv for argv in argv_list if str(greece_country_place.id) in argv]
    assert matching_jobs
    for argv in matching_jobs:
        assert argv[argv.index("--geo") + 1] == "EL"


def test_eurostat_regional_runs_once_for_all_regions() -> None:
    from tourism_pulse_api.scheduler.jobs import (
        SCHEDULED_ADAPTERS,
        build_argv_eurostat_regional,
    )

    assert build_argv_eurostat_regional(None) == [[]]  # type: ignore[arg-type]
    (adapter,) = [a for a in SCHEDULED_ADAPTERS if a.name == "eurostat_regional"]
    assert adapter.interval_minutes == 7 * 24 * 60


@pytest.fixture()
def statistics_only_places(db_session, hungary) -> list[Place]:
    """EU-scale places: a NUTS 2 region, a NUTS 3 area and an Urban Audit
    city, all with coordinates and one named like a KSH tourism area."""
    places = [
        Place(
            destination_id=hungary.id,
            name=name,
            place_type=place_type,
            latitude=47.5,
            longitude=19.0,
        )
        for name, place_type in (
            ("Budapest", "area"),
            ("Közép-Magyarország", "region"),
            ("Scheduler test city", "city"),
        )
    ]
    db_session.add_all(places)
    db_session.commit()
    return places


@pytest.mark.parametrize(
    "build_argv",
    [
        build_argv_weather,
        build_argv_osm,
        build_argv_openaq,
        build_argv_opensky,
        build_argv_gdacs,
        build_argv_wikipedia,
        build_argv_youtube,
        build_argv_gdelt,
        build_argv_events,
        build_argv_ksh,
    ],
)
def test_live_adapters_skip_statistics_only_places(
    db_session, budapest, statistics_only_places, build_argv
) -> None:
    ids = {argv[argv.index("--place-id") + 1] for argv in build_argv(db_session)}

    assert not ids & {str(place.id) for place in statistics_only_places}
