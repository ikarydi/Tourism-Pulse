"""Tests for the Airbnb scaffold - asserts the "not configured" contract,
not real ingestion. No network, no DB. See ingestion/airbnb/client.py's
module docstring for why this adapter is a scaffold rather than a live
integration."""

import pytest
from tourism_pulse_api.ingestion.airbnb import __main__ as airbnb_main
from tourism_pulse_api.ingestion.airbnb.client import (
    SourceNotConfiguredError,
    fetch_listings,
)


def test_fetch_listings_always_raises() -> None:
    with pytest.raises(SourceNotConfiguredError):
        fetch_listings(place_id=1)


def test_fetch_listings_error_mentions_no_public_api() -> None:
    with pytest.raises(SourceNotConfiguredError, match="public API"):
        fetch_listings(place_id=1)


def test_fetch_listings_accepts_arbitrary_kwargs_without_side_effects() -> None:
    with pytest.raises(SourceNotConfiguredError):
        fetch_listings(place_id=1, room_type="entire_home")


def test_main_returns_exit_code_one(capsys) -> None:
    exit_code = airbnb_main.run(["--place-id", "1"])

    assert exit_code == 1


def test_main_writes_explanation_to_stderr(capsys) -> None:
    airbnb_main.run(["--place-id", "1"])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Airbnb" in captured.err
