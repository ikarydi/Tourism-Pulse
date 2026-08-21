"""Reproducible Eurostat tourism ingestion command.

    python -m tourism_pulse_api.ingestion.eurostat --place-id 400 --geo AT
    python -m tourism_pulse_api.ingestion.eurostat --place-id 400 --geo AT --dry-run
    python -m tourism_pulse_api.ingestion.eurostat --place-id 400 --geo AT --month 2026-05
    python -m tourism_pulse_api.ingestion.eurostat --place-id 400 --geo AT --backfill
    python -m tourism_pulse_api.ingestion.eurostat --place-id 400 --geo AT --metric occupancy_rate
    python -m tourism_pulse_api.ingestion.eurostat --place-id 400 --geo AT --metric arrivals
    python -m tourism_pulse_api.ingestion.eurostat --place-id 400 --geo AT --metric capacity --backfill

`--metric` selects which Eurostat dataset to ingest (default: nights):

    nights          tour_occ_nim  - nights spent, seasonally normalized, feeds `demand`
    arrivals        tour_occ_arm  - tourist arrivals, raw/archival only, feeds no dimension
    occupancy_rate  tour_occ_mnor - net bed-place occupancy rate, feeds `demand` directly
    capacity        tour_cap_nat  - bed-places (annual), seasonally normalized, feeds `capacity`

None of these have a regional breakdown - each is one number per country
per period - so this is meant to be ingested against a country-level place
(mirroring how ingestion.ksh_capacity attaches Hungary's national capacity
to a "Hungary" place), not a city-specific one.

`capacity` is published *annually*, not monthly, unlike the other three -
every observation is internally stamped as December of its year, so
`--month` for it must be given as `YYYY-12` (e.g. `--month 2024-12`), and
`--backfill` pulls one point per year rather than per month.

`--geo` is a Eurostat geo code, which is not always ISO 3166-1: Greece is
`EL` (not `GR`), the United Kingdom is `UK` (not `GB`). Most other EU
countries match their ISO code (AT, CZ, PL, DE, ...).

By default, a run ingests only the single most recently published period.
Pass --backfill once to load the full available history for a place, which
is also what the nights and capacity metrics' seasonal normalization needs
to compute a real baseline instead of reporting "insufficient_baseline".

Running the same period twice never creates a duplicate signal: it upserts
in place, keyed on (place_id, signal_type, observed_at, source).
"""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass

from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.eurostat.client import (
    build_arrivals_request_url,
    build_capacity_request_url,
    build_occupancy_request_url,
    build_request_url,
    fetch_arrivals,
    fetch_capacity,
    fetch_occupancy_rate,
    fetch_tourism_nights,
)
from tourism_pulse_api.ingestion.eurostat.parser import (
    EUROSTAT_SOURCE_NAME,
    EurostatObservation,
    parse_eurostat_arrivals,
    parse_eurostat_capacity,
    parse_eurostat_occupancy_rate,
    parse_eurostat_tourism_nights,
)
from tourism_pulse_api.ingestion.eurostat.service import (
    build_arrivals_preview,
    build_capacity_preview,
    build_occupancy_preview,
    build_preview,
    select_observations,
    upsert_arrivals_signal,
    upsert_capacity_signal,
    upsert_occupancy_rate_signal,
    upsert_tourism_nights_signal,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation


@dataclass(frozen=True)
class MetricSpec:
    fetch: Callable[..., str]
    build_url: Callable[..., str]
    parse: Callable[[str], list[EurostatObservation]]
    # A "seasonal" metric's preview needs the full series (for a baseline);
    # a "direct" metric's preview only needs the one observation.
    build_preview: Callable[..., object]
    needs_full_series_for_preview: bool
    upsert: Callable[..., tuple[object | None, bool, object]]
    not_found_label: str
    # Eurostat dataset code - disambiguates raw archive rows, since all
    # four metrics share the single "eurostat" Source row.
    dataset: str


METRICS: dict[str, MetricSpec] = {
    "nights": MetricSpec(
        fetch=fetch_tourism_nights,
        build_url=build_request_url,
        parse=parse_eurostat_tourism_nights,
        build_preview=build_preview,
        needs_full_series_for_preview=True,
        upsert=upsert_tourism_nights_signal,
        not_found_label="nights-spent",
        dataset="eurostat_tour_occ_nim",
    ),
    "arrivals": MetricSpec(
        fetch=fetch_arrivals,
        build_url=build_arrivals_request_url,
        parse=parse_eurostat_arrivals,
        build_preview=build_arrivals_preview,
        needs_full_series_for_preview=False,
        upsert=upsert_arrivals_signal,
        not_found_label="arrivals",
        dataset="eurostat_tour_occ_arm",
    ),
    "occupancy_rate": MetricSpec(
        fetch=fetch_occupancy_rate,
        build_url=build_occupancy_request_url,
        parse=parse_eurostat_occupancy_rate,
        build_preview=build_occupancy_preview,
        needs_full_series_for_preview=False,
        upsert=upsert_occupancy_rate_signal,
        not_found_label="occupancy-rate",
        dataset="eurostat_tour_occ_mnor",
    ),
    "capacity": MetricSpec(
        fetch=fetch_capacity,
        build_url=build_capacity_request_url,
        parse=parse_eurostat_capacity,
        build_preview=build_capacity_preview,
        needs_full_series_for_preview=True,
        upsert=upsert_capacity_signal,
        not_found_label="capacity",
        dataset="eurostat_tour_cap_nat",
    ),
}


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tourism_pulse_api.ingestion.eurostat",
        description="Ingest country-level tourism data from Eurostat.",
    )
    parser.add_argument(
        "--place-id",
        type=int,
        required=True,
        help="Place to attach the ingested signal(s) to (a country-level place).",
    )
    parser.add_argument(
        "--geo",
        type=str,
        required=True,
        help="Eurostat geo code (e.g. AT, CZ, PL; note EL for Greece, UK for United Kingdom).",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="nights",
        choices=sorted(METRICS),
        help="Which Eurostat dataset to ingest (default: nights).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested without writing to the database.",
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Ingest a single YYYY-MM period instead of the latest one.",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Ingest every available published month, not just the latest.",
    )
    parser.add_argument(
        "--json-path",
        type=str,
        default=None,
        help="Read a local Eurostat JSON response instead of fetching (e.g. for testing).",
    )
    return parser


def _load_response_text(*, spec: MetricSpec, geo: str, json_path: str | None) -> str:
    if json_path is not None:
        with open(json_path, encoding="utf-8") as handle:
            return handle.read()

    return spec.fetch(geo=geo)


def _preview_dict(
    spec: MetricSpec,
    observation: EurostatObservation,
    observations: list[EurostatObservation],
) -> dict:
    if spec.needs_full_series_for_preview:
        return spec.build_preview(observation, observations).as_dict()

    return spec.build_preview(observation).as_dict()


def run(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    spec = METRICS[args.metric]

    try:
        text = _load_response_text(spec=spec, geo=args.geo, json_path=args.json_path)
    except OSError as exc:
        print(f"Failed to read Eurostat data: {exc}", file=sys.stderr)
        return 1

    try:
        observations = spec.parse(text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not observations:
        print(
            f"No {spec.not_found_label} observations found for geo {args.geo!r}.",
            file=sys.stderr,
        )
        return 1

    try:
        targets = select_observations(
            observations,
            month=args.month,
            backfill=args.backfill,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not targets:
        print(f"No observation found for period {args.month!r}.", file=sys.stderr)
        return 1

    source_url = spec.build_url(geo=args.geo)

    if args.dry_run:
        for observation in targets:
            preview = _preview_dict(spec, observation, observations)
            print(f"[DRY RUN] {preview['period']}")
            for key, value in preview.items():
                if key == "period":
                    continue
                print(f"    {key}: {value}")
            print()
        return 0

    db = SessionLocal()

    try:
        place = db.get(Place, args.place_id)

        if place is None:
            print(f"Place {args.place_id} not found.", file=sys.stderr)
            return 1

        source_observation = archive_raw_observation(
            db,
            source_name=EUROSTAT_SOURCE_NAME,
            dataset=spec.dataset,
            raw_payload=text,
            content_type="application/json",
            place_id=args.place_id,
            source_url=source_url,
        )

        for observation in targets:
            preview = _preview_dict(spec, observation, observations)

            signal, created, gate = spec.upsert(
                db,
                place_id=args.place_id,
                observation=observation,
                source_url=source_url,
                source_observation_id=source_observation.id,
            )

            if signal is None:
                reject_reasons = "; ".join(
                    outcome.detail or outcome.check_name
                    for outcome in gate.outcomes
                    if not outcome.passed and outcome.severity == "reject"
                )
                print(f"[REJECTED] {preview['period']}: {reject_reasons}", file=sys.stderr)
                continue

            preview["signal_id"] = signal.id
            preview["action"] = "created" if created else "updated"

            print(f"[INGESTED] {preview['period']}")
            for key, value in preview.items():
                if key == "period":
                    continue
                print(f"    {key}: {value}")
            print()
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
