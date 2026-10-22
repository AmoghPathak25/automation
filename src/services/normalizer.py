from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import re
import pandas as pd
from src.config import load_yaml
STANDARD_FIELDS = ["material_code", "description", "grade", "dimensions", "warehouse", "storage_location", "batch_number", "quantity_on_hand", "quantity_available", "unit_of_measure", "stock_date", "last_movement_date", "currency", "reference_price", "minimum_approved_price", "customer_id", "customer_name"]
DATE_ALIASES = {
    "stock_date": {"stock date", "receipt date", "date of receipt", "posting date"},
    "last_movement_date": {"last movement date", "last movement", "movement date"},
}

def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()

def _text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    result = str(value).strip()
    return result if result and result.lower() not in {"nan", "none", "nat"} else None

def _preserve_material(value: object) -> str | None:
    result = _text(value)
    if result is None:
        return None
    # Excel numeric cells may irreversibly lose leading zeros; flagging is done by the validator.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return result

def normalize_frame(frame: pd.DataFrame, source_file: str, source_sheet: str = "") -> pd.DataFrame:
    mappings = load_yaml("config/column_mappings.yaml", {})
    source_lookup = {_key(column): column for column in frame.columns}
    field_sources: dict[str, object] = {}
    for field in STANDARD_FIELDS:
        aliases = mappings.get(field, [])
        extra_aliases = DATE_ALIASES.get(field, set())
        candidate_keys = [_key(field), *(_key(alias) for alias in aliases), *extra_aliases]
        field_sources[field] = next((source_lookup[key] for key in candidate_keys if key in source_lookup), None)
    rows = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for index, original in frame.iterrows():
        row = {field: None for field in STANDARD_FIELDS}
        raw = {}
        for field, column in field_sources.items():
            if column is not None:
                value = original[column]
                row[field] = _preserve_material(value) if field == "material_code" else _text(value)
                if field in {"stock_date", "last_movement_date"} and value is not None and not pd.isna(value):
                    row[field] = value if isinstance(value, (datetime, pd.Timestamp)) else str(value).strip()
                raw[str(column)] = None if pd.isna(value) else str(value)
        row.update({"source_file": Path(source_file).name, "source_sheet": source_sheet or "", "source_row": int(index) + 2,
                    "import_timestamp": timestamp, "validation_status": "NEW", "validation_errors": [],
                    "original_values": raw, "source_material_numeric": bool(field_sources["material_code"] is not None and isinstance(original[field_sources["material_code"]], (int, float)) and not pd.isna(original[field_sources["material_code"]]))})
        rows.append(row)
    return pd.DataFrame(rows)
