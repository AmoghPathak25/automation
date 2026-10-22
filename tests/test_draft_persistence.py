import json
import pandas as pd
import pytest
from src.database.repository import Repository

def test_save_exact_edited_text_and_reload_without_duplicate(tmp_path):
    repo = Repository(tmp_path / "drafts.sqlite3")
    request = {"request_key": "request-a", "subject": "Availability", "to": "customer@example.invalid"}
    draft_id = repo.save_draft({"body": "initial draft", "request": request, "status": "DRAFT"})
    edited = {"body": "Exact edited text from the widget", "request": request, "status": "DRAFT"}
    assert repo.save_draft(edited, draft_id=draft_id) == draft_id
    assert repo.get_draft(draft_id)["payload"]["body"] == "Exact edited text from the widget"
    # A fresh repository instance is equivalent to a Streamlit rerun/reload.
    reloaded = Repository(tmp_path / "drafts.sqlite3")
    assert reloaded.get_draft(draft_id)["payload"]["body"] == "Exact edited text from the widget"
    assert len(reloaded.drafts()) == 1
    assert reloaded.get_draft(draft_id)["payload"]["request"] == request
    assert reloaded.get_draft(draft_id)["status"] == "DRAFT"
    assert any(event["event_type"] == "DRAFT_UPDATED" for event in reloaded.audit_events())


def test_different_drafts_keep_separate_payloads(tmp_path):
    repo = Repository(tmp_path / "drafts.sqlite3")
    first = repo.save_draft({"body": "first", "request_key": "a"})
    second = repo.save_draft({"body": "second", "request_key": "b"})
    repo.save_draft({"body": "edited first", "request_key": "a"}, draft_id=first)
    assert repo.get_draft(first)["payload"]["body"] == "edited first"
    assert repo.get_draft(second)["payload"]["body"] == "second"
    assert len(repo.drafts()) == 2

def test_empty_body_and_missing_draft_are_rejected(tmp_path):
    repo = Repository(tmp_path / "drafts.sqlite3")
    with pytest.raises(ValueError, match="cannot be empty"):
        repo.save_draft({"body": "   "})
    with pytest.raises(KeyError, match="was not found"):
        repo.save_draft({"body": "text"}, draft_id="missing-id")
    assert repo.drafts() == []
