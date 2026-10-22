import pandas as pd
from src.services.inventory_matcher import match_request
from src.services.email_classifier import parse_email_text

def inventory():
    return pd.DataFrame([
        {"material_code": "M1", "grade": "G1", "dimensions": "10 mm", "quantity_available": "5", "validation_status": "VALIDATED"},
        {"material_code": "M2", "grade": "G1", "dimensions": "10 mm", "quantity_available": "5", "validation_status": "VALIDATED"},
        {"material_code": "M3", "grade": "G1", "dimensions": "10 mm", "quantity_available": "5", "validation_status": "NEEDS_REVIEW"},
    ])

def test_exact_match():
    result = match_request({"material_code": "M1", "grade": "G1", "dimensions": "10 mm", "requested_quantity": 3}, inventory())
    assert result["match_status"] == "EXACT_MATCH"

def test_possible_alternative_not_exact():
    result = match_request({"material_code": "UNKNOWN", "grade": "G1", "dimensions": "10 mm", "requested_quantity": 3}, inventory())
    assert result["match_status"] == "POSSIBLE_ALTERNATIVE"
    assert all(row["material_code"] != "UNKNOWN" for row in result["matches"])

def test_ambiguous_request_and_malformed_email():
    result = match_request({"material_code": None, "grade": None, "dimensions": None}, inventory())
    assert result["match_status"] == "INSUFFICIENT_DATA"
    parsed = parse_email_text("broken header\n\nNeed stock please")
    assert parsed["category"] == "Unknown / manual review"
    assert parsed["confidence"] == "LOW"
