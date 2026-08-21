"""Shared raw-archive (Bronze layer, spec section 12) helper.

Every ingestion adapter's `__main__.py` calls `archive_raw_observation`
right before its real (non-dry-run) write, passing the same in-memory
string its `client.py` already fetched - `client.py`/`parser.py` stay
untouched, preserving their "pure fetch" / "pure parse" contracts.

Archiving happens from the in-memory fetch result rather than by writing
then re-reading from the database: the fetched text is byte-identical
either way, so there is no correctness difference, but round-tripping
through the DB before parsing would force `--dry-run` to touch the
database too, breaking its documented zero-write guarantee.
"""

import hashlib
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.source import Source
from tourism_pulse_api.db.models.source_observation import SourceObservation


class UnknownSourceError(ValueError):
    """Raised when `source_name` has no row in the `sources` registry.

    Every adapter's source must be seeded via migration first (see the
    `add_sources_table` migration) - this closes the class of bug where a
    new adapter's source was simply absent from the old reliability dict
    (as `osm` was) and nobody noticed.
    """


def archive_raw_observation(
    db: Session,
    *,
    source_name: str,
    dataset: str,
    raw_payload: str,
    content_type: str,
    place_id: int | None = None,
    source_url: str | None = None,
    retrieved_at: datetime | None = None,
    schema_version: str | None = None,
) -> SourceObservation:
    source = (
        db.query(Source)
        .filter(Source.name == source_name.strip().lower())
        .one_or_none()
    )

    if source is None:
        raise UnknownSourceError(
            f"Source {source_name!r} is not registered in the sources "
            "table. Add a seed row via migration before ingesting from it."
        )

    observation = SourceObservation(
        source_id=source.id,
        dataset=dataset,
        place_id=place_id,
        retrieved_at=retrieved_at or datetime.now(UTC),
        source_url=source_url,
        raw_payload=raw_payload,
        content_type=content_type,
        checksum=hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
        schema_version=schema_version,
    )

    db.add(observation)
    db.commit()
    db.refresh(observation)

    return observation
