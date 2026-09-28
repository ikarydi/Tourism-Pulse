"""Publishing live forecasts to the public record."""

import csv
import hashlib
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from tourism_pulse_api.db.models import Destination, Forecast, Place
from tourism_pulse_api.db.models.forecast import BACKTEST, LIVE
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.forecasting.publish import (
    commit_and_push,
    granted,
    last_published,
    pending_batch,
    run,
    timestamp_request,
    write_batch,
)
from tourism_pulse_api.scheduler.jobs import SCHEDULED_ADAPTERS

# Other tests store live forecasts too; these use issue dates after theirs,
# with a manifest cut-off that hides everything earlier.
FUTURE = datetime(2031, 3, 1, 12, 0, tzinfo=UTC)


def test_timestamp_request_is_a_well_formed_rfc3161_query() -> None:
    digest = hashlib.sha256(b"forecasts").digest()
    request = timestamp_request(digest, nonce=b"\x81\x02\x03\x04\x05\x06\x07\x08")

    assert request[0] == 0x30 and request[1] == len(request) - 2
    assert request[2:5] == b"\x02\x01\x01"  # version 1
    assert digest in request
    assert b"\x02\x08\x01\x02\x03\x04\x05\x06\x07\x08" in request  # nonce kept positive
    assert request.endswith(b"\x01\x01\xff")  # certReq TRUE


def test_only_granted_responses_count() -> None:
    assert granted(bytes.fromhex("3082000a" + "3003020100" + "0000"))
    assert not granted(bytes.fromhex("3082000a" + "3003020102" + "0000"))  # rejection


def _forecast(db, place_id: int, target: datetime, issued_at: datetime, kind: str = LIVE) -> None:
    db.add(
        Forecast(
            place_id=place_id,
            signal_type="tourism_nights",
            kind=kind,
            model="POOL_GR_WG",
            issued_at=issued_at,
            origin=datetime(2031, 1, 31, tzinfo=UTC),
            target=target,
            horizon=target.month - 1,
            point=Decimal("1000"),
            low_80=Decimal("900"),
            high_80=Decimal("1100"),
            low_95=Decimal("800"),
            high_95=Decimal("1200"),
        )
    )


def _manifest(directory: Path, issued_to: datetime) -> None:
    (directory / "manifest.csv").write_text(
        "batch,published_at,issued_from,issued_to,forecasts,places,sha256,timestamp_authority\n"
        f"earlier,{issued_to.isoformat()},{issued_to.isoformat()},{issued_to.isoformat()},"
        "0,0,x,y\n"
    )


def test_batches_hold_each_live_forecast_once(tmp_path: Path) -> None:
    _manifest(tmp_path, datetime(2030, 12, 31, tzinfo=UTC))
    db = SessionLocal()
    try:
        destination = Destination(country_code="QP", name="PUB country")
        db.add(destination)
        db.flush()
        place = Place(
            destination_id=destination.id, name="Publandia", place_type="country", nuts_code="QP"
        )
        db.add(place)
        db.flush()
        _forecast(db, place.id, datetime(2031, 2, 28, tzinfo=UTC), FUTURE)
        _forecast(db, place.id, datetime(2031, 3, 31, tzinfo=UTC), FUTURE)
        _forecast(db, place.id, datetime(2031, 4, 30, tzinfo=UTC), FUTURE, kind=BACKTEST)
        db.commit()

        first = pending_batch(db, tmp_path, datetime(2031, 3, 2, tzinfo=UTC))
        assert first is not None
        digest = write_batch(tmp_path, first, timestamp=lambda d: b"token:" + d)

        # Published: nothing pending until a later live forecast is issued.
        assert pending_batch(db, tmp_path, datetime(2031, 3, 3, tzinfo=UTC)) is None
        _forecast(db, place.id, datetime(2031, 5, 31, tzinfo=UTC), datetime(2031, 4, 1, tzinfo=UTC))
        db.commit()
        second = pending_batch(db, tmp_path, datetime(2031, 4, 2, tzinfo=UTC))
    finally:
        db.close()

    assert [(r["place"], r["target"], r["validated"]) for r in first.rows] == [
        ("Publandia", "2031-02", "yes"),
        ("Publandia", "2031-03", "yes"),
    ]
    folder = tmp_path / "batches" / first.name
    content = (folder / "forecasts.csv").read_bytes()
    assert hashlib.sha256(content).hexdigest() == digest
    assert (folder / "forecasts.csv.tsr").read_bytes() == b"token:" + bytes.fromhex(digest)
    assert (folder / "forecasts.csv.sha256").read_text().startswith(digest)
    assert last_published(tmp_path) == FUTURE
    assert second is not None and [r["target"] for r in second.rows] == ["2031-05"]
    with (tmp_path / "manifest.csv").open() as handle:
        assert [row["forecasts"] for row in csv.DictReader(handle)] == ["0", "2"]


def test_a_batch_is_committed_without_touching_earlier_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    _manifest(tmp_path, datetime(2030, 1, 1, tzinfo=UTC))
    subprocess.run(["git", "-C", str(tmp_path), "add", "manifest.csv"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "start"], check=True)

    from tourism_pulse_api.forecasting.publish import Batch

    batch = Batch(
        name="2031-03-02T000000Z",
        published_at=datetime(2031, 3, 2, tzinfo=UTC),
        rows=[{"place_id": 1, "target": "2031-02"}],
        issued_from=FUTURE,
        issued_to=FUTURE,
    )
    folder = tmp_path / "batches" / batch.name
    folder.mkdir(parents=True)
    (folder / "forecasts.csv").write_text("place_id,target\n1,2031-02\n")
    with (tmp_path / "manifest.csv").open("a") as handle:
        handle.write("next,a,b,c,1,1,x,y\n")

    commit_and_push(tmp_path, batch, push=False)

    log = subprocess.run(
        ["git", "-C", str(tmp_path), "log", "--format=%s", "--name-only", "-1"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert log.startswith("Forecast batch 2031-03-02T000000Z: 1 forecasts for 1 places")
    assert f"batches/{batch.name}/forecasts.csv" in log


def test_publishing_is_skipped_without_a_target(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FORECAST_PUBLISH_DIR", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    assert run([]) == 0


def test_publishing_runs_hourly_on_the_schedule() -> None:
    adapters = {adapter.name: adapter for adapter in SCHEDULED_ADAPTERS}
    assert adapters["forecast_publish"].interval_minutes == 60
    assert adapters["forecast_publish"].build_argv(None) == [[]]  # type: ignore[arg-type]
