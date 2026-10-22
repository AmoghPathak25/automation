from __future__ import annotations
from datetime import date, datetime
import math
import pandas as pd
from src.config import load_yaml

REQUIRED_CLEARANCE_RULES = ("minimum_stock_quantity", "ageing_threshold_days", "excess_stock_threshold", "required_stock_freshness_days")


def _rules_valid(rules: object) -> tuple[bool, list[str]]:
    if not isinstance(rules, dict):
        return False, ["Clearance rules must be a YAML mapping/object."]
    problems = [f"{key} is not configured." for key in REQUIRED_CLEARANCE_RULES if key not in rules or rules.get(key) is None]
    for key in REQUIRED_CLEARANCE_RULES:
        value = rules.get(key)
        if value is not None:
            try:
                number = float(value)
                if number < 0 or not math.isfinite(number):
                    problems.append(f"{key} must be a finite non-negative number.")
                if key in {"ageing_threshold_days", "required_stock_freshness_days"} and not number.is_integer():
                    problems.append(f"{key} must be a whole number of days.")
            except (TypeError, ValueError):
                problems.append(f"{key} must be a finite non-negative number.")
    return not problems, problems

def _configured_date(value: object, date_format: str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime, pd.Timestamp)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).date()
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if date_format:
        try:
            parsed = datetime.strptime(text, date_format)
            if parsed.strftime(date_format) == text:
                return parsed.date()
        except (TypeError, ValueError):
            return None
        return None
    try:
        parsed = date.fromisoformat(text)
        return parsed if parsed.isoformat() == text else None
    except ValueError:
        return None

def evaluate_clearance(inventory: pd.DataFrame | list[dict], rules: dict | None = None, date_format: str | None = None) -> pd.DataFrame:
    frame = inventory.copy() if isinstance(inventory, pd.DataFrame) else pd.DataFrame(inventory)
    settings = load_yaml("config/settings.yaml", {})
    if date_format is None:
        date_format = settings.get("app", {}).get("date_format")
    try:
        loaded_rules = rules if rules is not None else load_yaml("config/clearance_rules.yaml", {})
    except Exception:
        loaded_rules = None
    configured, rule_problems = _rules_valid(loaded_rules)
    if frame.empty: return pd.DataFrame(columns=["material_code", "clearance_status", "clearance_reason"])
    output = []
    rules = loaded_rules if isinstance(loaded_rules, dict) else {}
    for row in frame.to_dict(orient="records"):
        reasons = []
        missing = list(rule_problems)
        excluded = []
        if row.get("validation_status") != "VALIDATED": excluded.append("Inventory row is not VALIDATED.")
        if not configured:
            output.append({**row, "clearance_status": "NOT_CONFIGURED", "clearance_reason": "Approved clearance rules are incomplete or invalid; decisions are disabled.", "clearance_review": "NEEDS_REVIEW", "unconfigured_rules": missing, "exclusions": excluded, "reference_price": row.get("reference_price"), "currency": row.get("currency"), "proposed_quantity": None, "proposed_price": None, "approval_ready": False})
            continue
        qty = _float(row.get("quantity_on_hand"))
        if rules.get("minimum_stock_quantity") is not None:
            if qty is None: excluded.append("Stock quantity unavailable or invalid.")
            elif qty < float(rules["minimum_stock_quantity"]): excluded.append("Below configured minimum stock quantity.")
            else: reasons.append(f"Quantity {qty:g} meets configured minimum {rules['minimum_stock_quantity']}.")
        if rules.get("excess_stock_threshold") is not None:
            if qty is None: excluded.append("Stock quantity unavailable or invalid.")
            elif qty < float(rules["excess_stock_threshold"]): excluded.append("Below configured excess-stock threshold.")
            else: reasons.append(f"Quantity {qty:g} meets configured excess-stock threshold {rules['excess_stock_threshold']}.")
        if rules.get("ageing_threshold_days") is not None:
            stock_date = _configured_date(row.get("stock_date"), date_format)
            if stock_date is None: excluded.append("Stock date unavailable, invalid, or inconsistent with configured date format.")
            else:
                age = (date.today() - stock_date).days
                if age < int(rules["ageing_threshold_days"]): excluded.append(f"Stock age {age} days is below configured threshold.")
                else: reasons.append(f"Stock age {age} days meets configured threshold {rules['ageing_threshold_days']} days.")
        if rules.get("required_stock_freshness_days") is not None:
            imported = pd.to_datetime(row.get("import_timestamp"), errors="coerce", utc=True)
            if pd.isna(imported): excluded.append("Import timestamp unavailable; freshness cannot be checked.")
            else:
                age = (pd.Timestamp.now(tz="UTC") - imported).days
                if age > int(rules["required_stock_freshness_days"]): excluded.append(f"Inventory export is stale ({age} days).")
                else: reasons.append("Inventory export meets configured freshness.")
        if excluded:
            status = "EXCLUDED"
        elif missing:
            status = "NOT_CONFIGURED"
        else:
            status = "CANDIDATE"
        output.append({**row, "clearance_status": status, "clearance_reason": "; ".join(reasons) if reasons else "No qualification established.", "clearance_review": "NEEDS_REVIEW", "unconfigured_rules": missing, "exclusions": excluded,
                       "reference_price": row.get("reference_price"), "currency": row.get("currency"), "proposed_quantity": None, "proposed_price": None, "approval_ready": False})
    return pd.DataFrame(output).astype({"approval_ready": object})

def _float(value):
    try: return float(str(value).replace(",", "")) if value not in (None, "") else None
    except (TypeError, ValueError): return None


def calculate_offer_price(reference_price: object, currency: str | None, minimum_price: object, discount_percent: object, configured_max_discount: object) -> dict:
    try:
        reference, floor, discount, maximum = map(float, (reference_price, minimum_price, discount_percent, configured_max_discount))
    except (TypeError, ValueError):
        return {"approval_ready": False, "status": "NEEDS_REVIEW", "reason": "Price, currency, minimum price, or discount rule is missing/invalid."}
    if not all(map(pd.notna, (reference, floor, discount, maximum))) or reference < 0 or floor < 0 or maximum < 0:
        return {"approval_ready": False, "status": "NEEDS_REVIEW", "reason": "Conflicting or invalid price/discount values."}
    if not currency: return {"approval_ready": False, "status": "NEEDS_REVIEW", "reason": "Currency is missing."}
    if discount < 0 or discount > maximum: return {"approval_ready": False, "status": "NEEDS_REVIEW", "reason": "Discount exceeds the configured maximum or is negative."}
    proposed = round(reference * (1 - discount / 100), 4)
    if proposed < floor: return {"approval_ready": False, "status": "NEEDS_REVIEW", "reason": "Proposed price is below the approved minimum price."}
    return {"approval_ready": False, "status": "PENDING_APPROVAL", "proposed_price": proposed, "currency": currency, "reason": "Pricing checks passed; human approval is still required."}
