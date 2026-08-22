def validate_dimension_weights() -> None:
    total = sum(DIMENSION_WEIGHTS.values())

    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            f"Dimension weights must sum to 1.0, got {total}"
        )

    if any(
        weight < 0.0 or weight > 1.0
        for weight in DIMENSION_WEIGHTS.values()
    ):
        raise ValueError("Dimension weights must be between 0 and 1")


# Rebalanced from the original 4-dimension set (demand 0.35 / capacity 0.25
# / events 0.20 / environment 0.20) to make room for two new dimensions
# added alongside the GDACS and Eurostat-economics adapters: `risk` (hazard
# alerts - previously had no dimension to feed) and `economic` (tourism
# spend/employment - previously an entirely unimplemented source category).
# Demand keeps the largest share (still the single strongest tourism-
# activity indicator); the four narrower dimensions are weighted lower than
# either original headline dimension. Still required to sum to 1.0 -
# enforced by validate_dimension_weights() below.
DIMENSION_WEIGHTS: dict[str, float] = {
    "demand": 0.25,
    "capacity": 0.20,
    "events": 0.15,
    "environment": 0.15,
    "risk": 0.15,
    "economic": 0.10,
}
