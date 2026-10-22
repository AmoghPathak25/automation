from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd
from src.utils.file_safety import validate_file

def workbook_sheets(path: str | Path) -> list[str]:
    validate_file(path)
    suffix = Path(path).suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise ValueError("Worksheet selection is available only for .xlsx/.xlsm workbooks.")
    # pandas/openpyxl reads cell values only. VBA macros are never executed.
    return list(pd.ExcelFile(path, engine="openpyxl").sheet_names)

def read_tabular(path: str | Path, sheet_name: str | None = None) -> tuple[pd.DataFrame, str]:
    source = Path(path)
    validate_file(source)
    suffix = source.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        sheets = workbook_sheets(source)
        chosen = sheet_name or sheets[0]
        if chosen not in sheets:
            raise ValueError(f"Worksheet {chosen!r} does not exist. Available sheets: {sheets}")
        frame = pd.read_excel(source, sheet_name=chosen, engine="openpyxl", dtype=object)
        frame.attrs["source_sheet"] = chosen
        return frame, chosen
    if suffix == ".csv":
        try:
            frame = pd.read_csv(source, dtype=object, encoding="utf-8-sig", keep_default_na=False)
        except UnicodeDecodeError:
            frame = pd.read_csv(source, dtype=object, encoding="cp1252", keep_default_na=False)
        frame.attrs["source_sheet"] = "CSV"
        return frame, "CSV"
    raise ValueError(f"{suffix} is not a supported tabular input.")

def preview_workbook(path: str | Path, sheet_name: str | None = None, rows: int = 10) -> tuple[list[str], pd.DataFrame]:
    sheets = workbook_sheets(path)
    chosen = sheet_name or sheets[0]
    frame, _ = read_tabular(path, chosen)
    return sheets, frame.head(rows)
