"""Turn a question into a chart spec - constrained to the catalog.

The LLM only *chooses*: metric ids from the catalog, place ids from the
places table, a chart type from a fixed list. Its JSON answer is then
validated like any user-built spec; anything not in the catalog is
rejected, so the model cannot invent data or write queries. Same Groq
provider and model as pulse.narrative.
"""

import json
import logging

from groq import Groq, GroqError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from tourism_pulse_api.explore.catalog import build_catalog
from tourism_pulse_api.explore.query import resolve_places
from tourism_pulse_api.schemas.explore import ViewSpec
from tourism_pulse_api.settings import settings

logger = logging.getLogger(__name__)

_MAX_OUTPUT_TOKENS = 700

_SYSTEM_PROMPT = """You turn a tourism analyst's question into a chart specification.
Answer with one JSON object and nothing else:
{
  "title": short chart title,
  "explanation": one sentence on what the chart shows and any caveat,
  "spec": {
    "query": {
      "metrics": [1-4 metric ids, copied exactly from METRICS],
      "places": [place ids from PLACES] or null for all places,
      "place_type": "destination" or "country" or null,
      "grain": "day" | "month" | "year",
      "start": "YYYY-MM-DD" or null,
      "end": "YYYY-MM-DD" or null
    },
    "chart": {
      "type": "line" | "bar" | "scatter" | "heatmap" | "map" | "table",
      "x": "time" | "place",
      "collapse": "latest" | "avg" | "sum" | "max" | "min",
      "color": "place" | "metric" | null
    }
  }
}
Rules: use only ids that appear in METRICS and PLACES. Trends over time: line
(x=time). Comparing places on one metric: bar (x=place). Relationship between two
metrics across places: scatter (x=place, first metric on the x axis, second on the
y axis). Many places over time: heatmap. Geographic view of one metric: map.
Match the grain to the metric's native grain (annual metrics: year). If the
question cannot be answered from METRICS, pick the closest metrics and say so in
the explanation."""


class AskUnavailableError(RuntimeError):
    pass


class AskInvalidError(ValueError):
    pass


def _context(db: Session) -> str:
    catalog = build_catalog(db)
    metrics = "\n".join(
        f"{metric.id} | {metric.label} | {metric.unit} | native grain {metric.grain} | "
        f"{metric.group}"
        for metric in catalog.values()
    )
    places = "\n".join(
        f"{place.id} | {place.name} | {place.place_type} | "
        f"{place.destination.country_code if place.destination else ''}"
        for place in resolve_places(db, None, None)
    )
    return f"METRICS:\n{metrics}\n\nPLACES:\n{places}"


def ask(db: Session, question: str) -> tuple[str, ViewSpec, str]:
    if not settings.groq_api_key:
        raise AskUnavailableError("Asking questions needs an LLM provider (set GROQ_API_KEY).")

    try:
        response = Groq(api_key=settings.groq_api_key).chat.completions.create(
            model=settings.narrative_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"{_context(db)}\n\nQUESTION: {question}"},
            ],
            max_tokens=_MAX_OUTPUT_TOKENS,
            temperature=0.1,
            reasoning_effort="low",
            response_format={"type": "json_object"},
        )
    except GroqError as exc:
        logger.exception("ask failed for %r", question)
        raise AskUnavailableError("The LLM provider did not answer; try again.") from exc

    content = response.choices[0].message.content or ""
    try:
        answer = json.loads(content)
        spec = ViewSpec.model_validate(answer["spec"])
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
        raise AskInvalidError("Could not turn that question into a chart; try rephrasing.") from exc

    catalog = build_catalog(db)
    unknown = [metric for metric in spec.query.metrics if metric not in catalog]
    if unknown:
        raise AskInvalidError(f"The answer used metrics that do not exist: {', '.join(unknown)}")
    if spec.query.places:
        known = {place.id for place in resolve_places(db, spec.query.places, None)}
        spec.query.places = [place for place in spec.query.places if place in known] or None

    title = str(answer.get("title") or question)[:200]
    explanation = str(answer.get("explanation") or "")[:600]
    return title, spec, explanation
