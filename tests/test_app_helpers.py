from pathlib import Path
import pandas as pd
from src.app import _import_tabular_frame
from src.database.repository import Repository

def test_import_action_persists_normalized_data_and_reimport_is_idempotent(tmp_path):
    staged = tmp_path / "staged.xlsx"
    staged.write_bytes(b"synthetic staging bytes")
    repo = Repository(tmp_path / "app.sqlite3")
    frame = pd.DataFrame({"Material Number": ["000771"], "Unrestricted Stock": [5]})
    first = _import_tabular_frame(frame, "stock.xlsx", "Stock", staged, repo, {"app": {}})
    second = _import_tabular_frame(frame, "stock.xlsx", "Stock", staged, repo, {"app": {}})
    assert first == second
    assert len(repo.runs()) == 1
    assert repo.records()[0]["material_code"] == "000771"
