from datetime import datetime
from pathlib import Path
import pandas as pd
from src.reporting.csv_exporter import export_csv, unique_csv_path
from src.reporting.excel_exporter import export_excel, unique_export_path

def test_unique_timestamp_and_run_id_export_paths(tmp_path, monkeypatch):
    import src.reporting.excel_exporter as excel_exporter
    import src.reporting.csv_exporter as csv_exporter
    base = tmp_path / "validation_report.xlsx"
    timestamp = datetime(2026, 2, 3, 4, 5, 6, 123456)
    monkeypatch.setattr(excel_exporter, "datetime", type("FrozenDateTime", (), {"now": staticmethod(lambda: timestamp)}))
    monkeypatch.setattr(csv_exporter, "datetime", type("FrozenDateTime", (), {"now": staticmethod(lambda: timestamp)}))
    path = unique_export_path(base, "run/123")
    assert path.name == "validation_report_20260203_040506_123456_run123.xlsx"
    assert unique_csv_path(tmp_path / "clearance.csv").name == "clearance_20260203_040506_123456.csv"

def test_excel_and_csv_export_create_new_unique_files(tmp_path):
    data = pd.DataFrame({"material_code": ["00012"], "quantity": [4]})
    base = tmp_path / "report.xlsx"
    existing = tmp_path / "report_old.xlsx"
    existing.write_text("keep existing", encoding="utf-8")
    first = export_excel(data, base, "Report", run_id="abc")
    second = export_excel(data, base, "Report", run_id="abc")
    csv_one = export_csv(data, tmp_path / "report.csv", run_id="abc")
    csv_two = export_csv(data, tmp_path / "report.csv", run_id="abc")
    assert first != second and first.exists() and second.exists()
    assert csv_one != csv_two and csv_one.exists() and csv_two.exists()
    assert existing.read_text(encoding="utf-8") == "keep existing"
    assert pd.read_excel(first, dtype={"material_code": str}).iloc[0]["material_code"] == "00012"
    assert pd.read_csv(csv_one, dtype={"material_code": str}).iloc[0]["material_code"] == "00012"
