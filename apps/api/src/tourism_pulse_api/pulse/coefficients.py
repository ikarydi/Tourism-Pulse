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


DIMENSION_WEIGHTS: dict[str, float] = {
    "demand": 0.35,
    "capacity": 0.25,
    "events": 0.20,
    "environment": 0.20,
}
