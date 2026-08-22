from tourism_pulse_api.pulse.calculator import PulseResult
from tourism_pulse_api.pulse.confidence import ConfidenceResult


def interpret_pulse(
    *,
    pulse: PulseResult,
    confidence: ConfidenceResult,
) -> dict[str, object]:
    strengths: list[str] = []
    weaknesses: list[str] = []

    dimensions = {
        "Demand": pulse.demand,
        "Capacity": pulse.capacity,
        "Events": pulse.events,
        "Environment": pulse.environment,
        "Risk": pulse.risk,
        "Economic": pulse.economic,
    }

    missing_dimensions = [
        name
        for name, value in dimensions.items()
        if value == 0
    ]

    for name, value in dimensions.items():
        verb = "are" if name == "Events" else "is"

        if value >= 70:
            strengths.append(f"{name} {verb} strong")
        elif 0 < value < 40:
            weaknesses.append(f"{name} {verb} weak")

    for name in missing_dimensions:
        weaknesses.append(f"{name} data is missing")

    if confidence.coverage < 50:
        data_quality = "limited"
    elif confidence.coverage < 100:
        data_quality = "partial"
    else:
        data_quality = "complete"

    # Thresholds match the frontend's scoreStatus() (lib/format.ts) so the
    # headline's wording and the pulse score's own Weak/Moderate/Strong
    # badge never disagree - this branch used to have no genuinely low
    # tier at all, so a pulse of 0 was worded identically to a pulse of
    # 40 ("Moderate tourism activity based on available data").
    if pulse.pulse >= 70:
        headline = "Strong tourism activity"
    elif pulse.pulse >= 40:
        headline = "Moderate tourism activity"
    else:
        headline = "Weak tourism activity"

    if missing_dimensions:
        headline += " with limited coverage"

    return {
        "headline": headline,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "data_quality": data_quality,
    }
