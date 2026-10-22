from __future__ import annotations
from datetime import date, datetime
import math
import pandas as pd
from src.config import load_yaml

def _number(value: object) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "": return None
    try:
        number = float(str(value).replace(",", ""))
        return number if math.isfinite(number) else None
    except (TypeError, ValueError): return None

def _parse_configured_date(value: object, date_format: str | None) -> tuple[date | None, str | None]:
    if isinstance(value, (date, datetime, pd.Timestamp)):
        if pd.isna(value):
            return None, "Date is blank."
        return pd.Timestamp(value).date(), None
    text = str(value).strip()
    if not text:
        return None, "Date is blank."
    if not date_format:
        try:
            parsed = date.fromisoformat(text)
            if parsed.isoformat() == text:
                return parsed, None
        except ValueError:
            pass
        return None, "Date format is not configured; only unambiguous ISO dates are accepted."
    try:
        parsed = datetime.strptime(text, date_format)
    except (TypeError, ValueError):
        return None, f"Date does not match configured format {date_format!r}."
    if parsed.strftime(date_format) != text:
        return None, f"Date does not strictly match configured format {date_format!r}."
    return parsed.date(), None

def validate_inventory(records: pd.DataFrame, stale_after_days: int | None = None, date_format: str | None | object = ...) -> pd.DataFrame:
    result = records.copy(deep=True)
    configured_settings = load_yaml("config/settings.yaml", {})
    if date_format is ...:
        date_format = configured_settings.get("app", {}).get("date_format")
    if date_format is not None and not isinstance(date_format, str):
        date_format = None
    if result.empty:
        result.attrs["summary"] = {"rows_read": 0, "valid": 0, "needs_review": 0, "rejected": 1, "warnings": ["Worksheet is empty or malformed."]}
        return result
    required = configured_settings.get("inventory", {}).get("required_fields", ["material_code"])
    duplicate_fields = configured_settings.get("inventory", {}).get("duplicate_key_fields", ["material_code", "warehouse", "storage_location", "batch_number"])
    duplicate_fields = [field for field in duplicate_fields if field in result.columns]
    # Avoid treating all rows with missing optional key components as one duplicate group.
    duplicate_mask = pd.Series(False, index=result.index)
    if duplicate_fields:
        key_frame = result[duplicate_fields].fillna("").astype(str)
        has_material = result["material_code"].fillna("").astype(str).str.strip().ne("") if "material_code" in result else pd.Series(False, index=result.index)
        duplicate_mask.loc[has_material] = key_frame.loc[has_material].duplicated(keep=False)
    statuses = []
    errors_list = []
    warnings = []
    today = date.today()
    for idx, row in result.iterrows():
        errors, row_warnings = [], []
        for field in required:
            if field not in row or row.get(field) is None or pd.isna(row.get(field)) or str(row.get(field)).strip() == "":
                errors.append(f"Missing required field: {field}")
        if duplicate_mask.loc[idx]: errors.append("Duplicate material/location/batch key; not aggregated.")
        for field in ("quantity_on_hand", "quantity_available"):
            if field in row and (row.get(field) is None or pd.isna(row.get(field)) or str(row.get(field)).strip() == ""):
                errors.append(f"Missing quantity field: {field}.")
            elif row.get(field) is not None and not pd.isna(row.get(field)):
                quantity = _number(row.get(field))
                if quantity is None: errors.append(f"Unparseable {field}.")
                elif quantity < 0: errors.append(f"Negative {field}.")
        price = _number(row.get("reference_price"))
        floor = _number(row.get("minimum_approved_price"))
        if row.get("reference_price") is not None and price is None: errors.append("Invalid reference price.")
        if row.get("minimum_approved_price") is not None and floor is None: errors.append("Invalid minimum approved price.")
        if price is not None and price < 0: errors.append("Negative reference price.")
        if floor is not None and floor < 0: errors.append("Negative minimum approved price.")
        if price is not None and floor is not None and floor > price: errors.append("Minimum approved price exceeds reference price.")
        if (price is not None or floor is not None) and not row.get("currency"): errors.append("Price provided without currency.")
        for field in ("stock_date", "last_movement_date"):
            value = row.get(field)
            if field in row and (value is None or pd.isna(value) or str(value).strip() == ""):
                continue
            if value is not None and not pd.isna(value):
                parsed_date, parse_error = _parse_configured_date(value, date_format)
                if parse_error:
                    errors.append(f"Invalid {field}: {parse_error}")
                elif field == "stock_date" and stale_after_days is not None:
                    age = (today - parsed_date).days
                    if age > stale_after_days: errors.append(f"Stale stock report ({age} days; limit {stale_after_days}).")
                    if age < 0: errors.append("Stock date is in the future.")
        if row.get("source_material_numeric"): row_warnings.append("Material code came from a numeric cell; leading zeros may already have been lost in source.")
        unit = row.get("unit_of_measure")
        if unit: row_warnings.append(f"Unit preserved as supplied ({unit}); no conversion applied.")
        currency = row.get("currency")
        if currency: row_warnings.append(f"Currency preserved as supplied ({currency}); no conversion applied.")
        status = "REJECTED" if not row.get("source_row") else ("NEEDS_REVIEW" if errors or row_warnings else "VALIDATED")
        statuses.append(status); errors_list.append(errors + row_warnings); warnings.extend(row_warnings)
    result["validation_status"] = statuses
    result["validation_errors"] = errors_list
    result.attrs["summary"] = {"rows_read": len(result), "valid": statuses.count("VALIDATED"), "needs_review": statuses.count("NEEDS_REVIEW"), "rejected": statuses.count("REJECTED"), "warnings": list(dict.fromkeys(warnings))}
    return result
