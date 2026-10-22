from email.message import EmailMessage
import pandas as pd
from src.readers.pdf_reader import extract_pdf_text
from src.database.repository import Repository
from src.services.normalizer import normalize_frame
from src.services.validator import validate_inventory

def test_image_only_pdf_flagged_for_ocr(tmp_path):
    from pypdf import PdfWriter
    path = tmp_path / "blank.pdf"
    writer = PdfWriter(); writer.add_blank_page(width=72, height=72)
    with path.open("wb") as stream: writer.write(stream)
    result = extract_pdf_text(path)
    assert result["status"] == "NEEDS_REVIEW"
    assert "scanned" in result["message"]
    assert path.exists()

def test_repeat_import_dedupes_and_source_is_preserved(tmp_path):
    db = Repository(tmp_path / "test.sqlite3")
    source = tmp_path / "stock.csv"; source.write_text("Material\nA\n", encoding="utf-8")
    records = validate_inventory(normalize_frame(pd.DataFrame({"Material": ["A"]}), source.name, "CSV"))
    summary = records.attrs["summary"]
    from src.utils.file_safety import sha256_file
    first = db.save_import(source.name, sha256_file(source), "CSV", records, summary)
    again = db.save_import(source.name, sha256_file(source), "CSV", records, summary)
    assert first == again
    assert source.read_text(encoding="utf-8") == "Material\nA\n"
    assert len(db.runs()) == 1

def test_audit_run_references_source(tmp_path):
    db = Repository(tmp_path / "test.sqlite3")
    db.audit("CONFIG_REVIEWED", {"config": "clearance_rules.yaml"})
    assert db.audit_events()[0]["event_type"] == "CONFIG_REVIEWED"
