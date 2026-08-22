from tourism_pulse_api.classification.item_classifier import ItemCategory, classify_item


def test_classifies_an_event_title() -> None:
    assert classify_item("Budapest Wine Festival draws record crowds") == {ItemCategory.EVENTS}


def test_classifies_a_risk_title() -> None:
    assert classify_item("Wildfire forces evacuation near tourist resort") == {ItemCategory.RISK}


def test_classifies_an_economic_title() -> None:
    assert classify_item("Hotel prices surge amid inflation") == {ItemCategory.ECONOMIC}


def test_uncategorized_title_returns_empty_set() -> None:
    assert classify_item("Budapest Travel Guide 2026 - Top 10 Things to Do") == set()


def test_matches_multiple_categories() -> None:
    result = classify_item("Flood forces festival cancellation")

    assert result == {ItemCategory.RISK, ItemCategory.EVENTS}


def test_is_case_insensitive() -> None:
    assert classify_item("EARTHQUAKE STRIKES REGION") == {ItemCategory.RISK}


def test_matches_word_boundaries_not_substrings() -> None:
    # Deliberately no bare "fire" keyword (see the module's list comment)
    # precisely because benign compound words like "firewood" start with
    # it at a real word boundary - guard that it stays uncategorized.
    assert classify_item("Firewood sales rise ahead of winter") == set()


def test_stem_keyword_matches_inflected_forms() -> None:
    # "evacuat" is a deliberate stem - must match both "evacuated" and
    # "evacuation".
    assert classify_item("Residents evacuated after the storm") == {ItemCategory.RISK}
    assert classify_item("Evacuation order lifted") == {ItemCategory.RISK}
