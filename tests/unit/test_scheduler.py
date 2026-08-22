"""Tests for the scheduler's per-place/per-adapter failure isolation -
one place's run raising or exiting non-zero must not stop the rest of
that adapter's places."""

from tourism_pulse_api.scheduler.jobs import ScheduledAdapter
from tourism_pulse_api.scheduler.scheduler import run_adapter_once


def test_no_eligible_places_is_a_noop() -> None:
    calls: list[list[str]] = []

    adapter = ScheduledAdapter(
        name="test-adapter",
        run=lambda argv: calls.append(argv) or 0,
        build_argv=lambda db: [],
        interval_minutes=60,
    )

    run_adapter_once(adapter)

    assert calls == []


def test_runs_every_eligible_place() -> None:
    calls: list[list[str]] = []

    adapter = ScheduledAdapter(
        name="test-adapter",
        run=lambda argv: calls.append(argv) or 0,
        build_argv=lambda db: [["--place-id", "1"], ["--place-id", "2"]],
        interval_minutes=60,
    )

    run_adapter_once(adapter)

    assert calls == [["--place-id", "1"], ["--place-id", "2"]]


def test_one_place_raising_does_not_stop_the_rest() -> None:
    calls: list[list[str]] = []

    def flaky_run(argv: list[str]) -> int:
        if argv == ["--place-id", "1"]:
            raise RuntimeError("simulated network failure")
        calls.append(argv)
        return 0

    adapter = ScheduledAdapter(
        name="test-adapter",
        run=flaky_run,
        build_argv=lambda db: [["--place-id", "1"], ["--place-id", "2"]],
        interval_minutes=60,
    )

    # Must not raise - the whole point of per-place isolation.
    run_adapter_once(adapter)

    assert calls == [["--place-id", "2"]]


def test_one_place_exiting_nonzero_does_not_stop_the_rest() -> None:
    calls: list[list[str]] = []

    def partly_failing_run(argv: list[str]) -> int:
        calls.append(argv)
        return 1 if argv == ["--place-id", "1"] else 0

    adapter = ScheduledAdapter(
        name="test-adapter",
        run=partly_failing_run,
        build_argv=lambda db: [["--place-id", "1"], ["--place-id", "2"]],
        interval_minutes=60,
    )

    run_adapter_once(adapter)

    assert calls == [["--place-id", "1"], ["--place-id", "2"]]


def test_build_argv_raising_does_not_propagate() -> None:
    def broken_build_argv(db: object) -> list[list[str]]:
        raise RuntimeError("simulated DB error")

    adapter = ScheduledAdapter(
        name="test-adapter",
        run=lambda argv: 0,
        build_argv=broken_build_argv,
        interval_minutes=60,
    )

    # Must not raise - one adapter's build_argv failing must not take
    # down the scheduler process (or any other adapter's own schedule).
    run_adapter_once(adapter)
