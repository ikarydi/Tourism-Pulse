"""Source Registry reliability lookup (spec sections 6.5 / 13).

`pulse.reliability.SOURCE_RELIABILITY` used to be the only place source
reliability was defined. It is not deleted - it remains the seed data for
the `sources` table (see the `add_sources_table` migration) and the
fallback tier here for any source name that has not been registered in the
database, so a signal from a not-yet-cataloged source still gets a sane
(if conservative) reliability rather than failing.

`db.models.Source` is now the primary system-of-record: it is queryable,
editable without a code change, and carries the category/notes/base_url
metadata the dict never had room for.
"""

from sqlalchemy.orm import Session

from tourism_pulse_api.db.models.source import Source
from tourism_pulse_api.pulse.reliability import (
    get_source_reliability as get_dict_source_reliability,
)


def get_source_reliability(db: Session, source: str) -> float:
    normalized = source.strip().lower()

    row = (
        db.query(Source)
        .filter(Source.name == normalized, Source.is_active.is_(True))
        .one_or_none()
    )

    if row is not None:
        return float(row.reliability)

    return get_dict_source_reliability(source)
