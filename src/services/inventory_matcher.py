from __future__ import annotations
import re
from typing import Any
import pandas as pd

def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()

def match_request(request: dict, inventory: pd.DataFrame | list[dict]) -> dict:
    frame = inventory.copy() if isinstance(inventory, pd.DataFrame) else pd.DataFrame(inventory)
    material = _norm(request.get("material_code"))
    grade = _norm(request.get("grade"))
    dimensions = _norm(request.get("dimensions"))
    quantity = request.get("requested_quantity")
    critical_missing = [name for name, value in (("material code", material), ("grade", grade), ("dimensions", dimensions)) if not value]
    if frame.empty or "material_code" not in frame.columns:
        return {"match_status": "INSUFFICIENT_DATA" if critical_missing else "NO_MATCH_FOUND", "matches": [], "reason": "No imported inventory records are available."}
    usable = frame[frame.get("validation_status", pd.Series("NEEDS_REVIEW", index=frame.index)) == "VALIDATED"]
    def text_match(row, field, requested):
        return not requested or _norm(row.get(field)) == requested
    def quantity_ok(row):
        try:
            available = float(row.get("quantity_available") if row.get("quantity_available") not in (None, "") else row.get("quantity_on_hand"))
            return quantity is None or available >= float(quantity)
        except (TypeError, ValueError): return quantity is None
    exact = []
    alternatives = []
    for row in usable.to_dict(orient="records"):
        identity_match = _norm(row.get("material_code")) == material if material else False
        has_specification = bool(grade or dimensions)
        specs_match = has_specification and text_match(row, "grade", grade) and text_match(row, "dimensions", dimensions)
        if identity_match and specs_match and quantity_ok(row): exact.append(row)
        elif material and not identity_match and specs_match and quantity_ok(row): alternatives.append(row)
    if exact: return {"match_status": "EXACT_MATCH", "matches": exact, "reason": "Exact material, supplied specifications, quantity, and VALIDATED inventory matched."}
    if alternatives and not critical_missing: return {"match_status": "POSSIBLE_ALTERNATIVE", "matches": alternatives, "reason": "Specifications may match, but material identity differs; human confirmation required."}
    if critical_missing: return {"match_status": "INSUFFICIENT_DATA", "matches": [], "reason": "Missing required request details: " + ", ".join(critical_missing)}
    return {"match_status": "NO_MATCH_FOUND", "matches": [], "reason": "No validated inventory record supports this request."}
