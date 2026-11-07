import pytest
from tourism_pulse_api.pulse.felt_pressure import felt_pressure_share, mentions_felt_pressure


@pytest.mark.parametrize(
    "text",
    [
        "The old town was so crowded today",
        "Overtourism is ruining Santorini",
        "Every flat on my street is an Airbnb",
        "Rents went up again",
        "Είναι πολύ ΑΚΡΙΒΌ πια το Ηράκλειο",  # accents and case ignored
        "Túl sok turista van a Váci utcán",
        "Die Altstadt ist völlig überfüllt",
    ],
)
def test_matches_pressure_terms_in_each_language(text: str) -> None:
    assert mentions_felt_pressure(text)


@pytest.mark.parametrize(
    "text",
    [
        "Best beaches near Rethymno?",
        "My parents loved the thermal baths",  # "rent" only at a word start
        "The current is strong at Elafonisi",
    ],
)
def test_ignores_posts_without_pressure_terms(text: str) -> None:
    assert not mentions_felt_pressure(text)


def test_share_is_the_fraction_of_matching_posts() -> None:
    assert (
        felt_pressure_share(["so crowded", "lovely sunset", "too expensive", "ferry times"]) == 0.5
    )


def test_share_of_no_posts_is_none() -> None:
    assert felt_pressure_share([]) is None
