"""Import monthly GDELT series built by research/nowcast into signals.

python -m tourism_pulse_api.ingestion.gdelt_monthly
python -m tourism_pulse_api.ingestion.gdelt_monthly --data-dir research/nowcast/data
"""

import argparse
import csv
import io
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from tourism_pulse_api.db.models import Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.ksh.parser import SUPPORTED_REGIONS
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation

SOURCE_NAME = "gdelt"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[6] / "research" / "nowcast" / "data"
PER_MILLION = 1_000_000


def _month_end(month: str) -> datetime:
    year, number = int(month[:4]), int(month[5:7])
    following = date(year + (number == 12), number % 12 + 1, 1)
    last = date.fromordinal(following.toordinal() - 1)
    return datetime(last.year, last.month, last.day, tzinfo=UTC)


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.gdelt_monthly")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    countries_file = args.data_dir / "gdelt_full.csv"
    areas_file = args.data_dir / "gdelt_regional.csv"
    missing = [str(path) for path in (countries_file, areas_file) if not path.exists()]
    if missing:
        print(f"Missing research outputs: {', '.join(missing)}", file=sys.stderr)
        return 1
    current_month = f"{date.today():%Y-%m}"

    db = SessionLocal()
    try:
        countries = {
            place.nuts_code: place.id
            for place in db.query(Place).filter(Place.place_type == "country")
            if place.nuts_code
        }
        area_names = {region.place_name: key for key, region in SUPPORTED_REGIONS.items()}
        areas = {
            area_names[place.name]: place.id
            for place in db.query(Place).filter(Place.place_type == "destination")
            if place.name in area_names
        }

        values: list[tuple[int, str, str, float, str]] = []
        countries_text = countries_file.read_text()
        for row in _rows(countries_text):
            place_id = countries.get(row["geo"])
            if place_id is None or row["month"] >= current_month or int(row["corpus"]) <= 0:
                continue
            share = int(row["articles"]) / int(row["corpus"]) * PER_MILLION
            values.append(
                (place_id, "gdelt_tourism_share", row["month"], share, "per_million_articles")
            )
            if row["tone"]:
                values.append(
                    (place_id, "gdelt_tourism_tone", row["month"], float(row["tone"]), "tone")
                )
        areas_text = areas_file.read_text()
        for row in _rows(areas_text):
            place_id = areas.get(row["area"])
            if place_id is None or row["month"] >= current_month or int(row["corpus"]) <= 0:
                continue
            share = int(row["articles"]) / int(row["corpus"]) * PER_MILLION
            values.append(
                (place_id, "gdelt_attention_share", row["month"], share, "per_million_articles")
            )

        if args.dry_run:
            print(f"[DRY RUN] {len(values)} monthly values")
            return 0

        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset="gdelt_gkg_monthly",
            raw_payload="\n".join(
                [f"# {countries_file.name}", countries_text, f"# {areas_file.name}", areas_text]
            ),
            content_type="text/csv",
            source_url="https://data.gdeltproject.org/gkg/",
        )
        rows = [
            {
                "place_id": place_id,
                "signal_type": signal_type,
                "value": value,
                "unit": unit,
                "observed_at": _month_end(month),
                "source": SOURCE_NAME,
                "source_url": "https://data.gdeltproject.org/gkg/",
                "source_observation_id": observation.id,
            }
            for place_id, signal_type, month, value, unit in values
        ]
        for start in range(0, len(rows), 1000):
            statement = insert(Signal).values(rows[start : start + 1000])
            statement = statement.on_conflict_do_update(
                constraint="uq_signals_place_type_observed_source",
                set_={
                    "value": statement.excluded.value,
                    "source_observation_id": statement.excluded.source_observation_id,
                },
            )
            db.execute(statement)
        db.commit()
        print(f"[INGESTED] {len(rows)} monthly GDELT values")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
