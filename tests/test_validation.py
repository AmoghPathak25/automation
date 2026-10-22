import pandas as pd
from src.services.normalizer import normalize_frame
from src.services.validator import validate_inventory

def make_records(rows):
    return validate_inventory(normalize_frame(pd.DataFrame(rows), "synthetic.csv", "CSV"))

def test_missing_identifier_and_negative_quantity():
    rows = make_records({"Description": ["Missing id", "Negative"], "Qty": [1, -2]})
    assert rows.iloc[0].validation_status == "NEEDS_REVIEW"
    assert any("Missing required" in error for error in rows.iloc[0].validation_errors)
    assert any("Negative" in error for error in rows.iloc[1].validation_errors)

def test_duplicate_key_flagged_not_aggregated():
    result = make_records({"Material Number": ["A1", "A1"], "Warehouse": ["W", "W"], "Storage Location": ["S", "S"], "Batch": ["B", "B"], "Qty": [2, 3]})
    assert result.validation_status.tolist() == ["NEEDS_REVIEW", "NEEDS_REVIEW"]
    assert result.quantity_on_hand.tolist() == ["2", "3"]

def test_invalid_prices_and_currency():
    result = make_records({"Material": ["A", "B"], "Reference Price": [10, 20], "Minimum Price": [12, 5]})
    assert any("without currency" in error for error in result.iloc[0].validation_errors)
    assert any("exceeds" in error for error in result.iloc[0].validation_errors)

def test_stale_stock_export():
    result = make_records({"Material": ["A"], "Stock Date": ["2020-01-01"]})
    result = validate_inventory(result, stale_after_days=30, date_format="%Y-%m-%d")
    assert result.iloc[0].validation_status == "NEEDS_REVIEW"
    assert any("Stale" in error for error in result.iloc[0].validation_errors)
