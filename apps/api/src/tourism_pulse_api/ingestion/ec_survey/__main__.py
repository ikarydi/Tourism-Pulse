"""Load the Commission's tourism-sector business surveys.

    python -m tourism_pulse_api.ingestion.ec_survey
    python -m tourism_pulse_api.ingestion.ec_survey --dry-run

Stores monthly balances for EU27 country places from 2010: accommodation
confidence, past and expected demand, expected employment and prices, and
travel agencies' and tour operators' confidence and expected demand.
Re-running updates values in place (balances are not seasonally adjusted,
so revisions are rare).
"""

import argparse
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from tourism_pulse_api.db.models import Place, Signal
from tourism_pulse_api.db.session import SessionLocal
from tourism_pulse_api.ingestion.ec_survey.parser import (
    SURVEY_URL,
    UNIT,
    parse_workbook,
    release_candidates,
)
from tourism_pulse_api.ingestion.raw_archive import archive_raw_observation
from tourism_pulse_api.ingestion.wikipedia_monthly.articles import USER_AGENT

SOURCE_NAME = "european_commission"
SOURCE_PAGE = (
    "https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/"
    "business-and-consumer-surveys_en"
)
DEFAULT_CACHE_DIR = Path("data/ec_survey_cache")
_BATCH_ROWS = 1000


def _download(cache_dir: Path) -> tuple[str, bytes]:
    """The newest release available: (url, zip bytes)."""
    last_error: Exception | None = None
    for release in release_candidates(date.today()):
        url = SURVEY_URL.format(release=release)
        path = cache_dir / f"services_subsectors_{release}.zip"
        if path.exists() and path.read_bytes()[:2] == b"PK":
            return url, path.read_bytes()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
                body = response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            continue
        if not body.startswith(b"PK"):
            # A release not out yet answers with a web page, not a 404.
            last_error = ValueError(f"{url} is not a zip file")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        for older in cache_dir.glob("services_subsectors_*.zip"):
            if older != path:
                older.unlink()  # superseded: each release carries the full history
        return url, body
    raise OSError(f"no survey release found: {last_error}")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tourism_pulse_api.ingestion.ec_survey")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args(argv)

    try:
        url, body = _download(args.cache_dir)
        balances = parse_workbook(body)
    except (OSError, ValueError, KeyError) as exc:
        print(f"[FAILED] {exc}", file=sys.stderr)
        return 1
    latest = max((b.observed_at for b in balances), default=None)
    print(f"{len(balances)} balances from {url}, latest {latest:%Y-%m}" if latest else url)
    if args.dry_run:
        return 0

    db = SessionLocal()
    try:
        countries = {
            place.nuts_code: place.id
            for place in db.query(Place).filter(Place.place_type == "country")
            if place.nuts_code
        }
        rows = {
            (countries[b.country], b.signal_type, b.observed_at): b
            for b in balances
            if b.country in countries
        }
        observation = archive_raw_observation(
            db,
            source_name=SOURCE_NAME,
            dataset="services_subsectors_nsa",
            raw_payload="country,signal_type,month,value\n"
            + "".join(
                f"{b.country},{b.signal_type},{b.observed_at:%Y-%m},{b.value}\n" for b in balances
            ),
            content_type="text/csv",
            source_url=url,
        )
        values = [
            {
                "place_id": place_id,
                "signal_type": signal_type,
                "value": balance.value,
                "unit": UNIT,
                "observed_at": observed_at,
                "source": SOURCE_NAME,
                "source_url": SOURCE_PAGE,
                "source_observation_id": observation.id,
            }
            for (place_id, signal_type, observed_at), balance in rows.items()
        ]
        for start in range(0, len(values), _BATCH_ROWS):
            statement = insert(Signal).values(values[start : start + _BATCH_ROWS])
            statement = statement.on_conflict_do_update(
                constraint="uq_signals_place_type_observed_source",
                set_={
                    "value": statement.excluded.value,
                    "source_observation_id": statement.excluded.source_observation_id,
                },
            )
            db.execute(statement)
        db.commit()
        print(
            f"[INGESTED] {len(values)} monthly balances for {len({r[0] for r in rows})} countries"
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
