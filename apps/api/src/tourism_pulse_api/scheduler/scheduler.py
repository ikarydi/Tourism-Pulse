"""In-process ingestion scheduler runner.

One recurring APScheduler job per adapter in jobs.SCHEDULED_ADAPTERS.
Each job calls the adapter's run(argv) entrypoint directly - in-process,
no subprocess - once per currently-eligible place. Failures are
isolated at two levels: one place's run failing must not stop the rest
of that adapter's places, and one adapter's job failing (or simply
having zero eligible places right now) must not affect any other
adapter's own schedule.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]

from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.scheduler.jobs import SCHEDULED_ADAPTERS, ScheduledAdapter

logger = logging.getLogger("tourism_pulse_api.scheduler")


def run_adapter_once(adapter: ScheduledAdapter) -> None:
    db = SessionLocal()
    try:
        argv_list = adapter.build_argv(db)
    except Exception:
        logger.exception("failed to build jobs for adapter=%s", adapter.name)
        return
    finally:
        db.close()

    if not argv_list:
        logger.info("adapter=%s has no eligible places this run", adapter.name)
        return

    logger.info("adapter=%s running for %d place(s)", adapter.name, len(argv_list))

    for argv in argv_list:
        try:
            exit_code = adapter.run(argv)
            if exit_code != 0:
                logger.warning(
                    "adapter=%s argv=%s exited with code %d", adapter.name, argv, exit_code
                )
        except Exception:
            # One place failing (a network error, a rejected signal, an
            # unexpected response shape) must not stop the rest of this
            # adapter's places, or any other adapter's own schedule.
            logger.exception("adapter=%s argv=%s raised", adapter.name, argv)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()

    for adapter in SCHEDULED_ADAPTERS:
        scheduler.add_job(
            run_adapter_once,
            "interval",
            minutes=adapter.interval_minutes,
            args=[adapter],
            id=adapter.name,
            # Fire once immediately in addition to the interval, so a
            # freshly started scheduler doesn't sit idle for a full
            # interval before anything happens.
            next_run_time=datetime.now(),
        )

    return scheduler


def run() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    scheduler = build_scheduler()

    logger.info("starting scheduler with %d adapters", len(SCHEDULED_ADAPTERS))

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler stopped")

    return 0
