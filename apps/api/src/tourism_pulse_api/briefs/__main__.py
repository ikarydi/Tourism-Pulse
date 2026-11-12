"""Write a Destination Pressure Brief to an HTML file.

    python -m tourism_pulse_api.briefs --place "Kriti" --out crete.html
    python -m tourism_pulse_api.briefs --place-id 42 --out brief.html

Open the file in a browser and print to PDF (A4); the page is laid out
for print.
"""

import argparse
import sys
from pathlib import Path

from tourism_pulse_api.briefs import build_brief, find_place, render_html
from tourism_pulse_api.db.models import Place
from tourism_pulse_api.db.session import SessionLocal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--place", help="Place name, case-insensitive")
    target.add_argument("--place-id", type=int)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--licensee", help="Named on the cover as the licence holder")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        place = db.get(Place, args.place_id) if args.place_id else find_place(db, args.place)
        if place is None:
            print("Place not found.", file=sys.stderr)
            return 1
        brief = build_brief(db, place)
    finally:
        db.close()

    args.out.write_text(render_html(brief, licensee=args.licensee), encoding="utf-8")
    print(f"Wrote {args.out} ({len(brief.findings)} findings, {len(brief.sources)} sources)")
    for item in brief.withheld:
        print(f"Withheld: {item}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
