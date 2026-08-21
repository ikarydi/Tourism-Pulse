"""Tests for the Booking.com scaffold - asserts the "not configured"
contract, not real ingestion. No network, no DB. See
ingestion/booking/client.py's module docstring for why this adapter is a
scaffold rather than a live integration."""

import pytest
from tourism_pulse_api.ingestion.booking import __main__ as booking_main
from tourism_pulse_api.ingestion.booking.client import (
    SourceNotConfiguredError,
    fetch_availability,
)


def test_fetch_availability_always_raises() -> None:
    with pytest.raises(SourceNotConfiguredError):
        fetch_availability(place_id=1)


def test_fetch_availability_error_mentions_missing_credential() -> None:
    with pytest.raises(SourceNotConfiguredError, match="Partner Hub|Demand API|API key"):
        fetch_availability(place_id=1)


def test_fetch_availability_accepts_arbitrary_kwargs_without_side_effects() -> None:
    # The signature accepts **kwargs so future real params slot in without
    # a breaking change to callers - confirm it still just raises cleanly.
    with pytest.raises(SourceNotConfiguredError):
        fetch_availability(place_id=1, check_in="2026-09-01", check_out="2026-09-05")


def test_main_returns_exit_code_one(capsys) -> None:
    exit_code = booking_main.run(["--place-id", "1"])

    assert exit_code == 1


def test_main_writes_explanation_to_stderr(capsys) -> None:
    booking_main.run(["--place-id", "1"])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Booking.com" in captured.err
