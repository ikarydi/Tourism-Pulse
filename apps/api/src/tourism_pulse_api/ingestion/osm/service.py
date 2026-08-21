"""Orchestration for turning parsed OSM POIs into Attraction rows and a
Pulse-facing count signal.

Two distinct writes per ingestion run, for one category (hotel or
restaurant):

  1. One `Attraction` row per POI - the display/"digital twin" layer
     (per the master spec's attraction/hotel/restaurant entities),
     idempotently upserted on (source="osm", external_id).
  2. One aggregate `hotel_count` / `restaurant_count` Signal - the
     Pulse-facing layer, normalized via pulse.poi_density and feeding
     `capacity` alongside KSH/Eurostat's bed-place-based signals.

These are deliberately independent: a place can have its POI list without
that count driving Pulse math (not every ingestion run needs both), and
vice versa in principle, though in practice both are written together.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.attraction import Attraction
from tourism_pulse_api.db.models.signal import Signal
from tourism_pulse_api.ingestion.osm.parser import OSM_SOURCE_NAME, OsmPoi
from tourism_pulse_api.pulse.poi_density import normalize_poi_count

# category -> (signal_type, reference_count) - kept alongside the POI
# category vocabulary rather than duplicating it, since every category we
# ingest here has a corresponding count signal.
_COUNT_SIGNAL_TYPES: dict[str, str] = {
    "hotel": "hotel_count",
    "restaurant": "restaurant_count",
}


@dataclass(frozen=True)
class OsmIngestionPreview:
    source: str
    category: str
    poi_count: int
    normalized_value: float
    target_dimension: str
    sample_names: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "category": self.category,
            "poi_count": self.poi_count,
            "normalized_value": self.normalized_value,
            "target_dimension": self.target_dimension,
            "sample_names": self.sample_names,
        }


def build_preview(pois: list[OsmPoi], *, category: str, reference_count: int) -> OsmIngestionPreview:
    normalized = normalize_poi_count(len(pois), reference_count=reference_count)

    return OsmIngestionPreview(
        source=OSM_SOURCE_NAME,
        category=category,
        poi_count=len(pois),
        normalized_value=normalized,
        target_dimension="capacity",
        sample_names=[poi.name for poi in pois[:5]],
    )


def upsert_attraction(db: Session, *, place_id: int, poi: OsmPoi) -> tuple[Attraction, bool]:
    """Idempotently write one OSM POI as an Attraction row.

    Returns (attraction, created). Re-running with the same POI is a no-op
    beyond refreshing name/description/coordinates - it never creates a
    duplicate row for the same (source, external_id).

    Uniqueness is global on (source, external_id), same as Event - a
    physical POI has one true location, so it should only ever belong to
    one place. If two destinations' search radii overlap and both ingest
    the same POI, it stays attached to whichever place ingested it first
    (place_id is deliberately not overwritten on update); a minor
    attribution quirk for border-adjacent destinations, not incorrect data.
    """
    existing = (
        db.query(Attraction)
        .filter(
            Attraction.source == OSM_SOURCE_NAME,
            Attraction.external_id == poi.external_id,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.name = poi.name
        existing.description = poi.description
        existing.latitude = poi.latitude
        existing.longitude = poi.longitude
        db.commit()
        db.refresh(existing)
        return existing, False

    attraction = Attraction(
        place_id=place_id,
        name=poi.name,
        category=poi.category,
        description=poi.description,
        latitude=poi.latitude,
        longitude=poi.longitude,
        source=OSM_SOURCE_NAME,
        external_id=poi.external_id,
    )
    db.add(attraction)
    db.commit()
    db.refresh(attraction)
    return attraction, True


def upsert_poi_count_signal(
    db: Session,
    *,
    place_id: int,
    category: str,
    poi_count: int,
    observed_at: datetime | None = None,
) -> Signal:
    """Write (or overwrite) the aggregate POI-count Signal for one category.

    Unlike the government-statistics adapters, this is *not* upserted on a
    (place, signal_type, observed_at) key the way a monthly series is -
    OSM has no periods, only "the map as of now". Each run instead
    overwrites the place's single current count for this category, keyed
    on (place_id, signal_type, source) - re-running with fresher data
    replaces the stale count rather than accumulating a new row per run
    (which would dilute the Pulse dimension average the way an
    unpruned KSH/Eurostat backfill would - see those adapters' history).
    """
    if category not in _COUNT_SIGNAL_TYPES:
        raise ValueError(
            f"Unsupported category: {category!r}. "
            f"Expected one of: {sorted(_COUNT_SIGNAL_TYPES)}"
        )

    signal_type = _COUNT_SIGNAL_TYPES[category]
    resolved_observed_at = observed_at or datetime.now(UTC)

    existing = (
        db.query(Signal)
        .filter(
            Signal.place_id == place_id,
            Signal.signal_type == signal_type,
            Signal.source == OSM_SOURCE_NAME,
        )
        .one_or_none()
    )

    if existing is not None:
        existing.value = poi_count
        existing.observed_at = resolved_observed_at
        db.commit()
        db.refresh(existing)
        return existing

    signal = Signal(
        place_id=place_id,
        signal_type=signal_type,
        value=poi_count,
        unit="count",
        observed_at=resolved_observed_at,
        source=OSM_SOURCE_NAME,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal
