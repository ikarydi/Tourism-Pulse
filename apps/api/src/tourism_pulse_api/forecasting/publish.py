"""Publish live forecasts to a public git repository, with outside timestamps.

    python -m tourism_pulse_api.forecasting.publish
    python -m tourism_pulse_api.forecasting.publish --dry-run

The track record is only worth something if anyone can check that each
forecast existed before Eurostat published the month it forecasts. Each run
takes the live forecasts issued since the last published batch and writes
them to FORECAST_PUBLISH_DIR (a clone of the public repository):

    batches/<published-at>/forecasts.csv
    batches/<published-at>/forecasts.csv.sha256
    batches/<published-at>/forecasts.csv.tsr      RFC 3161 timestamp token
    manifest.csv                                  one row per batch

then commits and pushes. Git dates are set by whoever commits, so they prove
nothing on their own; the timestamp token is signed by an independent
authority (freetsa.org) over the file's SHA-256, and anyone can verify it
with openssl (see the repository's README).

Published files are never edited: a batch only ever adds a new directory.
Does nothing when FORECAST_PUBLISH_DIR is unset.
"""

import argparse
import csv
import hashlib
import io
import os
import secrets
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models import Forecast, Place
from tourism_pulse_api.db.models.forecast import LIVE
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.forecasting.service import POOLS

TSA_URL = "https://freetsa.org/tsr"
USER_AGENT = "TourismPulse/1.0 (https://github.com/ikarydi/Tourism-Pulse)"
MANIFEST_FIELDS = [
    "batch",
    "published_at",
    "issued_from",
    "issued_to",
    "forecasts",
    "places",
    "sha256",
    "timestamp_authority",
]
FORECAST_FIELDS = [
    "place_id",
    "place",
    "place_type",
    "code",
    "series",
    "validated",
    "model",
    "issued_at",
    "origin",
    "target",
    "horizon",
    "forecast",
    "low_80",
    "high_80",
    "low_95",
    "high_95",
]
# Only the country pool's model passed a pre-registered gate (Gate 2).
VALIDATED_PLACE_TYPES = set(POOLS["countries"][0])

# DER encoding of the SHA-256 AlgorithmIdentifier (OID 2.16.840.1.101.3.4.2.1, NULL).
_SHA256_ALGORITHM = bytes.fromhex("300d06096086480165030402010500")


def _der(tag: int, content: bytes) -> bytes:
    length = len(content)
    if length < 0x80:
        return bytes([tag, length]) + content
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(encoded)]) + encoded + content


def timestamp_request(digest: bytes, nonce: bytes | None = None) -> bytes:
    """An RFC 3161 TimeStampReq for a SHA-256 digest, asking for the
    authority's certificate in the reply."""
    if len(digest) != 32:
        raise ValueError("expected a SHA-256 digest")
    nonce = nonce or secrets.token_bytes(8)
    nonce = bytes([nonce[0] & 0x7F]) + nonce[1:]  # a positive INTEGER
    imprint = _der(0x30, _SHA256_ALGORITHM + _der(0x04, digest))
    body = _der(0x02, b"\x01") + imprint + _der(0x02, nonce) + _der(0x01, b"\xff")
    return _der(0x30, body)


def granted(response: bytes) -> bool:
    """Whether a TimeStampResp starts with status granted (0) or granted
    with modifications (1)."""
    # SEQUENCE { PKIStatusInfo SEQUENCE { status INTEGER, ... }, token }
    index = 2 if response[1] < 0x80 else 2 + (response[1] & 0x7F)
    if response[index] != 0x30:
        return False
    status = response[index + 2 : index + 5]
    return status[:2] == b"\x02\x01" and status[2] in (0, 1)


def request_timestamp(digest: bytes, url: str = TSA_URL) -> bytes:
    request = urllib.request.Request(
        url,
        data=timestamp_request(digest),
        headers={"Content-Type": "application/timestamp-query", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        body = response.read()
    if not body or not granted(body):
        raise RuntimeError("the timestamp authority did not grant a token")
    return body


@dataclass
class Batch:
    name: str
    published_at: datetime
    rows: list[dict]
    issued_from: datetime
    issued_to: datetime


def _month(moment: datetime) -> str:
    return f"{moment:%Y-%m}"


def last_published(directory: Path) -> datetime | None:
    manifest = directory / "manifest.csv"
    if not manifest.exists():
        return None
    with manifest.open(newline="") as handle:
        stamps = [datetime.fromisoformat(row["issued_to"]) for row in csv.DictReader(handle)]
    return max(stamps) if stamps else None


def pending_batch(db: Session, directory: Path, now: datetime) -> Batch | None:
    """Live forecasts issued after the last published batch."""
    cutoff = last_published(directory)
    query = (
        db.query(Forecast, Place)
        .join(Place, Place.id == Forecast.place_id)
        .filter(Forecast.kind == LIVE)
        .order_by(Forecast.issued_at, Place.name, Forecast.target)
    )
    if cutoff is not None:
        query = query.filter(Forecast.issued_at > cutoff)
    rows = []
    stamps = []
    for forecast, place in query:
        stamps.append(forecast.issued_at)
        rows.append(
            {
                "place_id": place.id,
                "place": place.name,
                "place_type": place.place_type,
                "code": place.nuts_code or place.nuts3_code or "",
                "series": forecast.signal_type,
                "validated": "yes" if place.place_type in VALIDATED_PLACE_TYPES else "no",
                "model": forecast.model,
                "issued_at": forecast.issued_at.astimezone(UTC).isoformat(),
                "origin": _month(forecast.origin),
                "target": _month(forecast.target),
                "horizon": forecast.horizon,
                "forecast": f"{forecast.point:.0f}",
                "low_80": f"{forecast.low_80:.0f}",
                "high_80": f"{forecast.high_80:.0f}",
                "low_95": f"{forecast.low_95:.0f}",
                "high_95": f"{forecast.high_95:.0f}",
            }
        )
    if not rows:
        return None
    return Batch(
        name=f"{now:%Y-%m-%dT%H%M%SZ}",
        published_at=now,
        rows=rows,
        issued_from=min(stamps),
        issued_to=max(stamps),
    )


def write_batch(directory: Path, batch: Batch, *, timestamp=request_timestamp) -> str:
    """Write the batch's files and manifest row; returns the SHA-256."""
    folder = directory / "batches" / batch.name
    folder.mkdir(parents=True, exist_ok=False)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FORECAST_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(batch.rows)
    content = buffer.getvalue().encode("utf-8")
    digest = hashlib.sha256(content).digest()
    (folder / "forecasts.csv").write_bytes(content)
    (folder / "forecasts.csv.sha256").write_text(f"{digest.hex()}  forecasts.csv\n")
    (folder / "forecasts.csv.tsr").write_bytes(timestamp(digest))

    manifest = directory / "manifest.csv"
    new_file = not manifest.exists()
    with manifest.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        if new_file:
            writer.writeheader()
        writer.writerow(
            {
                "batch": batch.name,
                "published_at": batch.published_at.isoformat(),
                "issued_from": batch.issued_from.astimezone(UTC).isoformat(),
                "issued_to": batch.issued_to.astimezone(UTC).isoformat(),
                "forecasts": len(batch.rows),
                "places": len({row["place_id"] for row in batch.rows}),
                "sha256": digest.hex(),
                "timestamp_authority": TSA_URL,
            }
        )
    return digest.hex()


def _git(directory: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed git arguments, no shell
        ["git", *args],  # noqa: S607
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def commit_and_push(directory: Path, batch: Batch, *, push: bool = True) -> None:
    _git(directory, "add", "manifest.csv", f"batches/{batch.name}")
    places = len({row["place_id"] for row in batch.rows})
    _git(
        directory,
        "commit",
        "-q",
        "-m",
        f"Forecast batch {batch.name}: {len(batch.rows)} forecasts for {places} places",
    )
    if push:
        _git(directory, "push", "-q", "origin", "HEAD")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.forecasting.publish")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-push", action="store_true", help="commit locally only")
    args = parser.parse_args(argv)

    target = os.environ.get("FORECAST_PUBLISH_DIR") or _from_dotenv("FORECAST_PUBLISH_DIR")
    if not target:
        print("[SKIPPED] FORECAST_PUBLISH_DIR is not set")
        return 0
    directory = Path(target)
    if not (directory / ".git").exists():
        print(f"[FAILED] {directory} is not a git clone", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        batch = pending_batch(db, directory, datetime.now(UTC))
    finally:
        db.close()
    if batch is None:
        print("[UP TO DATE] no live forecasts issued since the last batch")
        return 0
    if args.dry_run:
        print(f"[DRY RUN] batch {batch.name}: {len(batch.rows)} forecasts")
        return 0
    try:
        _git(directory, "pull", "-q", "--ff-only")
        digest = write_batch(directory, batch)
        commit_and_push(directory, batch, push=not args.no_push)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[FAILED] {exc}", file=sys.stderr)
        return 1
    print(f"[PUBLISHED] batch {batch.name}: {len(batch.rows)} forecasts, sha256 {digest}")
    return 0


def _from_dotenv(key: str) -> str | None:
    """The API reads .env through pydantic settings; this optional path
    stays out of Settings so the API never requires it."""
    env = Path(".env")
    if not env.exists():
        return None
    for line in env.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip() or None
    return None


if __name__ == "__main__":
    raise SystemExit(run())
