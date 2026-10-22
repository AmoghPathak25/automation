import pandas as pd
from src.services.clearance_engine import evaluate_clearance, calculate_offer_price

def test_unconfigured_clearance_rules_do_not_invent_candidate():
    rows = pd.DataFrame([{"material_code": "A", "quantity_on_hand": "100", "stock_date": "2020-01-01", "validation_status": "VALIDATED"}])
    result = evaluate_clearance(rows, {"minimum_stock_quantity": None, "ageing_threshold_days": None, "excess_stock_threshold": None, "required_stock_freshness_days": None})
    assert result.iloc[0].clearance_status == "NOT_CONFIGURED"
    assert result.iloc[0].approval_ready is False
    assert result.iloc[0].proposed_price is None

def test_price_below_approved_minimum_blocked():
    result = calculate_offer_price(100, "USD", 95, 10, 20)
    assert result["approval_ready"] is False
    assert "below" in result["reason"]

def test_price_within_rules_still_requires_human_approval():
    result = calculate_offer_price(100, "USD", 80, 10, 20)
    assert result["approval_ready"] is False
    assert result["status"] == "PENDING_APPROVAL"


def test_missing_empty_and_invalid_rules_disable_clearance():
    inventory = [{"material_code": "A", "quantity_on_hand": "10", "stock_date": "2020-01-01", "validation_status": "VALIDATED"}]
    for rules in (None, {}, {"minimum_stock_quantity": "unknown"}, "malformed"):
        result = evaluate_clearance(inventory, rules)
        assert result.iloc[0].clearance_status == "NOT_CONFIGURED"
        assert result.iloc[0].approval_ready is False

def test_complete_explicit_rules_can_produce_review_candidate():
    inventory = [{"material_code": "A", "quantity_on_hand": "100", "stock_date": "2020-01-01", "import_timestamp": pd.Timestamp.now(tz="UTC").isoformat(), "validation_status": "VALIDATED"}]
    rules = {"minimum_stock_quantity": 1, "ageing_threshold_days": 1, "excess_stock_threshold": 2, "required_stock_freshness_days": 1}
    result = evaluate_clearance(inventory, rules)
    assert result.iloc[0].clearance_status == "CANDIDATE"
    assert result.iloc[0].approval_ready is False

def test_conflicting_price_values_block_offer_approval():
    result = calculate_offer_price(100, "USD", 80, 10, float("nan"))
    assert result["approval_ready"] is False
    assert result["status"] == "NEEDS_REVIEW"
