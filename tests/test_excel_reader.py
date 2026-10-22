import pandas as pd
from src.readers.excel_reader import read_tabular, workbook_sheets
from src.services.normalizer import normalize_frame

def test_import_sheets_and_leading_zero_string(tmp_path):
    path = tmp_path / "synthetic.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"Material Number": ["000123"], "Unrestricted Stock": [5]}).to_excel(writer, sheet_name="Stock", index=False)
        pd.DataFrame({"Other": [1]}).to_excel(writer, sheet_name="Notes", index=False)
    assert workbook_sheets(path) == ["Stock", "Notes"]
    frame, sheet = read_tabular(path, "Stock")
    normalized = normalize_frame(frame, path.name, sheet)
    assert normalized.iloc[0]["material_code"] == "000123"
    assert normalized.iloc[0]["quantity_on_hand"] == "5"
    assert normalized.iloc[0]["source_row"] == 2
    assert path.exists()

def test_different_column_names(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text("SKU,Qty,Lot\n0010,3,B1\n", encoding="utf-8")
    frame, _ = read_tabular(path)
    row = normalize_frame(frame, path.name).iloc[0]
    assert row.material_code == "0010"
    assert row.quantity_on_hand == "3"
