from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from src.config import ROOT, load_yaml

def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)

class Repository:
    def __init__(self, db_path: str | Path | None = None):
        settings = load_yaml("config/settings.yaml", {})
        configured = db_path or settings.get("app", {}).get("database_path", "data/working/automation.sqlite3")
        self.path = Path(configured)
        if not self.path.is_absolute(): self.path = ROOT / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection
    def _initialize(self):
        with self.connect() as db:
            db.executescript("CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, source_file TEXT NOT NULL, source_hash TEXT NOT NULL, sheet TEXT, rows_read INTEGER NOT NULL, valid INTEGER NOT NULL, needs_review INTEGER NOT NULL, rejected INTEGER NOT NULL, status TEXT NOT NULL); CREATE TABLE IF NOT EXISTS records(run_id TEXT NOT NULL, source_row INTEGER, material_code TEXT, payload TEXT NOT NULL, PRIMARY KEY(run_id, source_row), FOREIGN KEY(run_id) REFERENCES runs(run_id)); CREATE TABLE IF NOT EXISTS audit_events(event_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, event_type TEXT NOT NULL, run_id TEXT, details TEXT NOT NULL); CREATE TABLE IF NOT EXISTS drafts(draft_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, run_id TEXT, payload TEXT NOT NULL, status TEXT NOT NULL); CREATE TABLE IF NOT EXISTS approvals(approval_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, draft_id TEXT NOT NULL, decision TEXT NOT NULL, notes TEXT);")
    def audit(self, event_type: str, details: dict, run_id: str | None = None):
        with self.connect() as db:
            db.execute("INSERT INTO audit_events VALUES(?,?,?,?,?)", (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), event_type, run_id, _json(details)))
    def save_import(self, source_file: str, source_hash: str, sheet: str, records, summary: dict) -> str:
        with self.connect() as db:
            prior = db.execute("SELECT run_id FROM runs WHERE source_hash=? AND sheet=?", (source_hash, sheet)).fetchone()
            if prior: return prior["run_id"]
            run_id = str(uuid.uuid4())
            status = "NEEDS_REVIEW" if summary.get("needs_review", 0) or summary.get("rejected", 0) else "VALIDATED"
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)", (run_id, datetime.now(timezone.utc).isoformat(), Path(source_file).name, source_hash, sheet, summary.get("rows_read", 0), summary.get("valid", 0), summary.get("needs_review", 0), summary.get("rejected", 0), status))
            for _, row in records.iterrows():
                payload = row.to_dict()
                db.execute("INSERT INTO records VALUES(?,?,?,?)", (run_id, payload.get("source_row"), payload.get("material_code"), _json(payload)))
            db.execute("INSERT INTO audit_events VALUES(?,?,?,?,?)", (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), "IMPORT", run_id, _json({"source_file": Path(source_file).name, "source_hash": source_hash, "sheet": sheet, **summary})))
            return run_id
    def runs(self) -> list[dict]:
        with self.connect() as db: return [dict(row) for row in db.execute("SELECT * FROM runs ORDER BY started_at DESC")]
    def records(self, run_id: str | None = None, validated_only: bool = False) -> list[dict]:
        query = "SELECT payload FROM records"; params = []
        if run_id: query += " WHERE run_id=?"; params.append(run_id)
        query += " ORDER BY rowid DESC"
        with self.connect() as db: rows = [json.loads(row[0]) for row in db.execute(query, params)]
        if validated_only: rows = [r for r in rows if r.get("validation_status") == "VALIDATED"]
        return rows
    def save_draft(self, payload: dict, run_id: str | None = None, draft_id: str | None = None) -> str:
        # Update in-place to preserve draft identity, status, and associated request.
        if not isinstance(payload, dict) or not str(payload.get("body", "")).strip():
            raise ValueError("Draft body cannot be empty.")
        if draft_id:
            with self.connect() as db:
                existing = db.execute("SELECT run_id FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
                if existing is None:
                    raise KeyError(f"Draft {draft_id} was not found; it may have been deleted.")
                db.execute("UPDATE drafts SET payload=? WHERE draft_id=?", (_json(payload), draft_id))
                preserved_run_id = run_id if run_id is not None else existing["run_id"]
            self.audit("DRAFT_UPDATED", {"draft_id": draft_id, "status": "DRAFT"}, preserved_run_id)
            return draft_id
        draft_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO drafts VALUES(?,?,?,?,?)", (draft_id, datetime.now(timezone.utc).isoformat(), run_id, _json(payload), "DRAFT"))
        self.audit("DRAFT_CREATED", {"draft_id": draft_id, "status": "DRAFT"}, run_id)
        return draft_id
    def drafts(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT draft_id, created_at, run_id, payload, status FROM drafts ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]
    def get_draft(self, draft_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT draft_id, created_at, run_id, payload, status FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        return {**dict(row), "payload": json.loads(row["payload"])} if row else None
    def run_for_source(self, source_file: str, source_hash: str | None = None) -> dict | None:
        with self.connect() as db:
            if source_hash:
                row = db.execute("SELECT * FROM runs WHERE source_file=? AND source_hash=? ORDER BY started_at DESC LIMIT 1", (Path(source_file).name, source_hash)).fetchone()
            else:
                row = db.execute("SELECT * FROM runs WHERE source_file=? ORDER BY started_at DESC LIMIT 1", (Path(source_file).name,)).fetchone()
        return dict(row) if row else None
    def audit_events(self) -> list[dict]:
        with self.connect() as db: return [dict(row) for row in db.execute("SELECT * FROM audit_events ORDER BY occurred_at DESC")]
