from banking_core.app.services.analytics import categorize


def test_deterministic_category_rules_and_unknown() -> None:
    assert categorize("Demo Supermarket Purchase") == "GROCERIES"
    assert categorize("Unmapped Fictional Merchant") == "UNKNOWN"
