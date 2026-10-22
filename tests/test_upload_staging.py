from pathlib import Path
import pytest
from src.utils.upload_staging import StagedUpload, safe_upload_basename

def test_same_filename_uploads_are_isolated_and_cleaned(tmp_path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"original source")
    root = tmp_path / "staging"
    with StagedUpload(root, "stock.xlsx", b"first") as first:
        first_path = first.path
        assert first_path.read_bytes() == b"first"
        with StagedUpload(root, "stock.xlsx", b"second") as second:
            assert second.path != first.path
            assert first.path.read_bytes() == b"first"
            assert second.path.read_bytes() == b"second"
        assert first.path.exists()
    assert not first_path.parent.exists()
    assert source.read_bytes() == b"original source"


def test_upload_is_cleaned_after_processing_failure(tmp_path):
    root = tmp_path / "staging"
    source = tmp_path / "original.csv"
    source.write_bytes(b"original")
    persistent_output = tmp_path / "report.xlsx"
    persistent_output.write_bytes(b"persistent report")
    with pytest.raises(RuntimeError):
        with StagedUpload(root, "bad.csv", b"body") as staged:
            path = staged.path
            raise RuntimeError("synthetic processing failure")
    assert not path.parent.exists()
    assert source.read_bytes() == b"original"
    assert persistent_output.read_bytes() == b"persistent report"


def test_unsafe_filename_cannot_escape_staging(tmp_path):
    assert safe_upload_basename(r"..\..\outside.xlsx") == "outside.xlsx"
    assert safe_upload_basename("../../outside.xlsx") == "outside.xlsx"
    with StagedUpload(tmp_path / "stage", r"..\..\outside.xlsx", b"safe") as staged:
        assert staged.path.parent == staged.directory
        assert staged.path.read_bytes() == b"safe"
    assert not (tmp_path / "outside.xlsx").exists()
