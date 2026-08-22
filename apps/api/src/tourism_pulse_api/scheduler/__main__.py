"""Long-running ingestion scheduler process.

    python -m tourism_pulse_api.scheduler

Registers one recurring job per adapter (see jobs.SCHEDULED_ADAPTERS)
and blocks until interrupted (Ctrl-C). Every adapter's run(argv)
entrypoint is called in-process - the scheduler only decides *when* and
*for which places*, reusing each adapter's already-battle-tested
fetch -> archive -> quality-gate -> upsert flow unchanged.
"""

from tourism_pulse_api.scheduler.scheduler import run

if __name__ == "__main__":
    raise SystemExit(run())
