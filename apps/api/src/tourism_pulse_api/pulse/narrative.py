"""LLM-written analyst narrative on top of pulse.insights' deterministic
evidence (spec section 24: "The Pulse engine remains deterministic...
LLMs handle: explanation, synthesis, natural-language interaction, report
generation" - this module is exactly that boundary, never the other way
around).

Uses Groq (console.groq.com) - a free-tier LLM provider, chosen
deliberately over a paid one - through one small function,
`generate_narrative`, so switching providers later is a one-file change,
not a rewrite touching every caller.

Gracefully degrades to `None` (never raises) whenever
`settings.groq_api_key` is unset or the API call fails for any reason -
the same pattern every other optional external dependency in this
codebase already follows (e.g. OpenAQ's optional key). A narrative is a
nice-to-have on top of an already-complete deterministic Pulse
calculation; it must never be able to break that calculation.
"""

import logging

from groq import Groq, GroqError

from tourism_pulse_api.pulse.calculator import PulseResult
from tourism_pulse_api.pulse.insights import DimensionEvidence
from tourism_pulse_api.settings import settings

logger = logging.getLogger(__name__)

_MAX_OUTPUT_TOKENS = 400
_TEMPERATURE = 0.4

_SYSTEM_PROMPT = (
    "You are a tourism-intelligence analyst writing a short briefing for "
    "a destination management professional. You are given a place's "
    "current Pulse score (0-100, overall tourism activity and conditions) "
    "broken into six dimensions - demand, capacity, events, environment, "
    "risk, economic - plus the actual evidence behind each dimension: "
    "real signal readings, real news articles, real videos, real events. "
    "If a PRESSURE section is present, it is a separate tourism-pressure "
    "index (0-100, higher means more strain on residents and "
    "infrastructure): never describe high pressure as a strength, and "
    "note that strong demand and high pressure can be true at once. "
    "Write one "
    "concise analyst-style paragraph (150-250 words) explaining what is "
    "happening and why, citing the SPECIFIC evidence you were given - "
    "name actual signal values and sources, actual article headlines, "
    "actual event names - rather than restating the scores in general "
    "terms. Never invent evidence you were not given. Plain prose only, "
    "no markdown formatting, no headings, no bullet points."
)


def _format_evidence(evidence: dict[str, DimensionEvidence]) -> str:
    lines: list[str] = []

    for dimension, dimension_evidence in evidence.items():
        lines.append(f"\n{dimension.upper()} = {dimension_evidence.value:.1f}/100")

        for signal in dimension_evidence.contributing_signals:
            unit = f" {signal.unit}" if signal.unit else ""
            lines.append(
                f"  - signal: {signal.signal_type} = {signal.value}{unit} "
                f"(source: {signal.source}, observed {signal.observed_at.date()})"
            )

        for article in dimension_evidence.related_articles:
            lines.append(f'  - article: "{article.title}" ({article.source})')

        for video in dimension_evidence.related_videos:
            channel = video.channel or "unknown channel"
            lines.append(f'  - video: "{video.title}" ({channel})')

        for event in dimension_evidence.related_events:
            lines.append(
                f'  - event: "{event.name}" ({event.event_type}), '
                f"starting {event.start_at.date()}"
            )

    return "\n".join(lines)


def generate_narrative(
    *,
    place_name: str,
    pulse: PulseResult,
    evidence: dict[str, DimensionEvidence],
    headline: str,
) -> str | None:
    if not settings.groq_api_key:
        return None

    user_prompt = (
        f"Place: {place_name}\n"
        f"Overall Pulse: {pulse.pulse:.1f}/100\n"
        f"Headline: {headline}\n"
        f"Evidence by dimension:\n{_format_evidence(evidence)}"
    )

    try:
        client = Groq(api_key=settings.groq_api_key)

        response = client.chat.completions.create(
            model=settings.narrative_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=_MAX_OUTPUT_TOKENS,
            temperature=_TEMPERATURE,
            # The default narrative_model (openai/gpt-oss-120b) is a
            # reasoning model: its internal "thinking" tokens count
            # against max_tokens same as the visible answer, and at
            # "medium"/default effort routinely ate the whole budget
            # before writing a word of narrative (finish_reason="length",
            # content cut off mid-sentence). "low" leaves the budget to
            # the actual paragraph. Harmless no-op on non-reasoning
            # models; if narrative_model is ever swapped to one that
            # rejects this kwarg outright, the broad except below still
            # degrades to None rather than breaking the pulse response.
            reasoning_effort="low",
        )
    except GroqError:
        logger.exception("narrative generation failed for %r", place_name)
        return None
    except Exception:
        # Never let narrative generation break the pulse response - it's
        # a nice-to-have on top of an already-complete deterministic
        # calculation, not a dependency of it.
        logger.exception("unexpected error generating narrative for %r", place_name)
        return None

    content = response.choices[0].message.content

    return content.strip() if content else None
