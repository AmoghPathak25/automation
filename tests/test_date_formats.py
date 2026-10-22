import pandas as pd
from src.services.normalizer import normalize_frame
from src.services.validator import validate_inventory

def validate_date(value, date_format):
    raw = pd.DataFrame({"Material Number": ["0001"], "Unrestricted Stock": [5], "Available Quantity": [5], "Stock Date": [value]})
    if date_format is False:
        return validate_inventory(normalize_frame(raw, "synthetic.xlsx", "Sheet1"), date_format=None).iloc[0]
    return validate_inventory(normalize_frame(raw, "synthetic.xlsx", "Sheet1"), date_format=date_format).iloc[0]

def test_configured_date_format_accepts_matching_date():
    row = validate_date("02/15/2026", "%m/%d/%Y")
    assert row.validation_status == "VALIDATED"

def test_configured_date_format_rejects_nonmatching_and_ambiguous_date():
    for value in ("2026-02-15", "01/02/2026"):
        row = validate_date(value, "%d-%m-%Y")
        assert row.validation_status == "NEEDS_REVIEW"
        assert any("does not match configured format" in error for error in row.validation_errors)

def test_no_date_format_rejects_ambiguous_but_accepts_iso():
    ambiguous = validate_date("01/02/2026", False)
    assert ambiguous.validation_status == "NEEDS_REVIEW"
    assert any("only unambiguous ISO dates" in error for error in ambiguous.validation_errors)
    iso = validate_date("2026-02-01", False)
    assert iso.validation_status == "VALIDATED"
