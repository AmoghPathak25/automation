from __future__ import annotations
from pathlib import Path
import hashlib
import pandas as pd
import streamlit as st
from src.config import ROOT, ensure_directories, load_yaml
from src.database.repository import Repository
from src.readers.excel_reader import read_tabular, workbook_sheets
from src.readers.pdf_reader import extract_pdf_text
from src.reporting.csv_exporter import export_csv
from src.reporting.excel_exporter import export_excel
from src.services.clearance_engine import evaluate_clearance
from src.services.draft_generator import generate_email_draft
from src.services.email_classifier import parse_email_text
from src.services.inventory_matcher import match_request
from src.services.normalizer import normalize_frame
from src.services.validator import validate_inventory
from src.utils.file_safety import sha256_file, validate_file
from src.utils.upload_staging import StagedUpload
st.set_page_config(page_title="Office Email Automation", layout="wide")
ensure_directories()
repo = Repository()
st.title("Office Email Automation")
st.caption("Local-first, review-required workflow assistant · dry run · no SAP or email sending")
settings = load_yaml("config/settings.yaml", {})

@st.cache_data(show_spinner=False)
def records_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)

def _import_tabular_frame(frame: pd.DataFrame, source_name: str, sheet: str, staged: Path, repo: Repository, settings: dict) -> str:
    normalized = normalize_frame(frame, source_name, sheet)
    app_settings = settings.get("app", {})
    validated = validate_inventory(normalized, stale_after_days=app_settings.get("stale_after_days"), date_format=app_settings.get("date_format"))
    summary = validated.attrs.get("summary", {})
    source_hash = sha256_file(staged)
    run_id = repo.save_import(source_name, source_hash, sheet, validated, summary)
    st.session_state["last_import"] = {"run_id": run_id, "source_hash": source_hash, "data": validated.to_dict(orient="records"), "summary": summary}
    return run_id

def _process_uploaded_file(uploaded, suffix: str, staged: Path, max_size: int, settings: dict, repo: Repository) -> None:
    validate_file(staged, max_size)
    if suffix in {".xlsx", ".xlsm", ".csv"}:
        sheets = workbook_sheets(staged) if suffix in {".xlsx", ".xlsm"} else ["CSV"]
        selected = st.selectbox("Worksheet", sheets) if len(sheets) > 1 else sheets[0]
        frame, sheet = read_tabular(staged, selected)
        st.write(f"Preview · {len(frame)} rows · {len(frame.columns)} source columns")
        st.dataframe(frame.head(20), width="stretch")
        if frame.empty or len(frame.columns) == 0:
            st.error("Empty or malformed worksheet. Nothing imported.")
        elif st.button("Normalize, validate, and import", type="primary", key=f"import_{id(uploaded)}"):
            run_id = _import_tabular_frame(frame, StagedUpload.safe_name(uploaded.name), sheet, staged, repo, settings)
            st.success(f"Import complete · Run {run_id}")
            st.json(st.session_state["last_import"]["summary"])
            st.dataframe(pd.DataFrame(st.session_state["last_import"]["data"]), width="stretch")
    elif suffix == ".pdf":
        if st.button("Extract PDF text", key=f"pdf_{id(uploaded)}"):
            result = extract_pdf_text(staged)
            repo.audit("ATTACHMENT_PROCESSED", {"source_file": Path(uploaded.name).name, "status": result["status"], "pages": result["pages"]})
            st.info(result["message"])
            if result["text"]: st.text_area("Extracted text (verify against source)", result["text"], height=350)
    elif suffix in {".txt", ".eml"}:
        raw = staged.read_text(encoding="utf-8", errors="replace")
        if suffix == ".txt":
            st.text_area("Email / copied content preview", raw, height=220)
            if st.button("Extract request details", key=f"email_{id(uploaded)}"):
                parsed = parse_email_text(raw)
                parsed["request_key"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                st.session_state["email_request"] = parsed
                st.success("Deterministic extraction complete; verify all fields.")
        else:
            from src.services.email_classifier import parse_eml
            parsed = parse_eml(staged)
            parsed["request_key"] = hashlib.sha256(staged.read_bytes()).hexdigest()
            st.session_state["email_request"] = parsed
            st.json({key: value for key, value in parsed.items() if key != "source_text"})
            if parsed.get("html_converted"):
                st.warning("HTML-only message was converted to text. Manually verify the message wording before relying on extracted details.")
            st.info("Attachments are listed, not automatically interpreted. Email remains unsent.")

pages = ["Overview", "Import files", "Validation report", "Inventory search", "Clearance candidates", "Email request review", "Offer draft review", "Processing history", "Configuration and rules"]
page = st.sidebar.radio("Sections", pages)
st.sidebar.info("Dry-run mode: enabled. Source files are read only. Nothing is sent externally.")
runs = repo.runs()
latest = runs[0] if runs else None
inventory_rows = repo.records()
inventory = records_frame(inventory_rows)

if page == "Overview":
    st.subheader("Overview")
    a,b,c,d = st.columns(4)
    a.metric("Processing runs", len(runs)); b.metric("Imported records", len(inventory))
    b_review = sum(1 for row in inventory_rows if row.get("validation_status") == "NEEDS_REVIEW")
    c.metric("Needs review", b_review); d.metric("Open drafts", len(repo.drafts()))
    st.warning("No real SAP export, reference price list, or business clearance policy was found in the project. Import local inputs and configure approved rules before operational decisions.")
    st.write("Latest processing run")
    st.json(latest or {"status": "No imports yet"})
    st.markdown("**Safety:** manually imported files only; no authenticated browser, SAP connection, external AI service, or message sending.")

elif page == "Import files":
    st.subheader("Import files")
    uploads = st.file_uploader("Select local exports or saved attachments", type=["xlsx", "xlsm", "csv", "pdf", "txt", "eml"], accept_multiple_files=True, help="Files are staged in unique temporary folders; source files are not modified.")
    for uploaded in uploads or []:
        original_name = StagedUpload.safe_name(uploaded.name)
        suffix = Path(original_name).suffix.lower()
        st.markdown(f"**Selected file:** `{original_name}` · {uploaded.size:,} bytes")
        max_size = int(settings.get("app", {}).get("max_upload_mb", 50)) * 1024 * 1024
        if uploaded.size > max_size:
            st.error(f"File exceeds configured limit ({max_size // (1024*1024)} MB).")
            continue
        try:
            with StagedUpload(ROOT / "data" / "working" / "uploads", original_name, uploaded.getvalue()) as staged_upload:
                _process_uploaded_file(uploaded, suffix, staged_upload.path, max_size, settings, repo)
        except Exception as exc:
            st.error(f"Could not process `{original_name}`: {exc}")
    last = st.session_state.get("last_import")
    if last:
        st.subheader("Most recent import result")
        st.json(last["summary"])
        st.dataframe(pd.DataFrame(last["data"]), width="stretch")

elif page == "Validation report":
    st.subheader("Validation report")
    if inventory.empty: st.info("Import a tabular file to see normalized records.")
    else:
        filtered = inventory
        if "validation_status" in inventory:
            statuses = st.multiselect("Status", sorted(inventory["validation_status"].dropna().unique()), default=sorted(inventory["validation_status"].dropna().unique()))
            filtered = inventory[inventory["validation_status"].isin(statuses)]
        st.dataframe(filtered, width="stretch")
        source_file = filtered.iloc[0].get("source_file") if not filtered.empty and "source_file" in filtered else None
        source_hash = st.session_state.get("last_import", {}).get("source_hash")
        source_run = repo.run_for_source(source_file, source_hash) if source_file else None
        run_id = source_run.get("run_id") if source_run else (latest.get("run_id") if latest else None)
        if st.button("Export validation report"):
            output = export_excel(filtered, ROOT / "data/output/validation_reports/validation_report.xlsx", "Validation", run_id=run_id)
            st.success(f"Saved local report: {output.relative_to(ROOT)}")
        if st.button("Export validation CSV"):
            csv_path = export_csv(filtered, ROOT / "data/output/validation_reports/validation_report.csv", run_id=run_id)
            st.success(f"Saved local report: {csv_path.relative_to(ROOT)}")

elif page == "Inventory search":
    st.subheader("Inventory search")
    query = st.text_input("Material code or description")
    if inventory.empty: st.info("No imported records yet.")
    else:
        view = inventory
        if query:
            mask = pd.Series(False, index=view.index)
            for field in ("material_code", "description", "grade", "dimensions"):
                if field in view: mask |= view[field].fillna("").astype(str).str.contains(query, case=False, regex=False)
            view = view[mask]
        st.dataframe(view, width="stretch")

elif page == "Clearance candidates":
    st.subheader("Explainable clearance evaluation")
    rules = load_yaml("config/clearance_rules.yaml", {})
    candidates = evaluate_clearance(inventory, rules, date_format=settings.get("app", {}).get("date_format"))
    source_file = inventory.iloc[0].get("source_file") if not inventory.empty and "source_file" in inventory else None
    source_hash = st.session_state.get("last_import", {}).get("source_hash")
    source_run = repo.run_for_source(source_file, source_hash) if source_file else None
    run_id = source_run.get("run_id") if source_run else (latest.get("run_id") if latest else None)
    if candidates.empty or candidates["clearance_status"].isin(["NOT_CONFIGURED", "NEEDS_REVIEW"]).any():
        st.warning("Clearance decisions are disabled: approved clearance rules are missing, incomplete, or invalid. Configure business-approved thresholds before making recommendations.")
    st.caption("Unset rules do not create candidates. This evaluation does not infer excess stock or propose offers/prices.")
    if not candidates.empty:
        statuses = st.multiselect("Evaluation status", sorted(candidates["clearance_status"].unique()), default=sorted(candidates["clearance_status"].unique()))
        view = candidates[candidates["clearance_status"].isin(statuses)]
        st.dataframe(view, width="stretch")
        chosen = st.selectbox("Inspect source record", list(range(len(view))), format_func=lambda i: f"{view.iloc[i].get('material_code')} · row {view.iloc[i].get('source_row')}") if not view.empty else None
        if chosen is not None: st.json(view.iloc[chosen].to_dict())
        x, y = st.columns(2)
        if x.button("Export clearance Excel"):
            path = export_excel(view, ROOT / "data/output/clearance_candidates/clearance_candidates.xlsx", "Candidates", run_id=run_id); st.success(f"Saved {path.relative_to(ROOT)}")
        if y.button("Export clearance CSV"):
            path = export_csv(view, ROOT / "data/output/clearance_candidates/clearance_candidates.csv", run_id=run_id); st.success(f"Saved {path.relative_to(ROOT)}")
    else: st.info("No inventory records to evaluate.")

elif page == "Email request review":
    st.subheader("Email request review")
    if "email_request" not in st.session_state:
        pasted = st.text_area("Paste saved email content (offline; never sent)", height=220)
        if st.button("Classify and extract"):
            parsed = parse_email_text(pasted)
            parsed["request_key"] = hashlib.sha256(pasted.encode("utf-8")).hexdigest()
            st.session_state["email_request"] = parsed
    request = st.session_state.get("email_request")
    if request:
        editable = dict(request)
        st.write("Extracted details · review/edit before matching")
        for key in ("sender", "subject", "category", "material_code", "grade", "dimensions", "requested_quantity"):
            editable[key] = st.text_input(key.replace("_", " ").title(), value=str(editable.get(key) or ""), key=f"email_{key}")
        try: editable["requested_quantity"] = float(editable["requested_quantity"]) if editable["requested_quantity"] else None
        except ValueError: st.warning("Requested quantity must be numeric."); editable["requested_quantity"] = None
        st.json({"uncertainties": request.get("uncertainties", []), "confidence": request.get("confidence", "LOW")})
        matching = match_request(editable, inventory)
        st.subheader(f"Match result: {matching['match_status']}")
        st.write(matching["reason"])
        if matching["matches"]: st.dataframe(pd.DataFrame(matching["matches"]), width="stretch")
        draft = generate_email_draft(editable, inventory, matching)
        request_key = request.get("request_key") or hashlib.sha256(str(request).encode("utf-8")).hexdigest()
        draft["request_key"] = request_key
        draft["request"] = editable
        existing_drafts = [item for item in repo.drafts() if item.get("payload", {}).get("request_key") == request_key]
        active_draft = existing_drafts[0] if existing_drafts else None
        draft_id = active_draft["draft_id"] if active_draft else None
        editor_id = str(draft_id or request_key)
        draft_widget_key = f"draft_body_{hashlib.sha256(editor_id.encode('utf-8')).hexdigest()[:16]}"
        initial_body = active_draft["payload"].get("body", draft["body"]) if active_draft else draft["body"]
        draft_body = st.text_area("Unsent draft (edit before saving)", value=initial_body, height=330, key=draft_widget_key)
        if st.button("Save draft for human review", key=f"save_draft_{hashlib.sha256(editor_id.encode('utf-8')).hexdigest()[:16]}"):
            draft["body"] = st.session_state[draft_widget_key]
            try:
                saved_id = repo.save_draft(draft, draft_id=draft_id)
                st.session_state["email_request"]["draft_id"] = saved_id
                st.success(f"Draft saved as {saved_id}; status PENDING_APPROVAL. Nothing sent.")
            except (ValueError, KeyError) as exc:
                st.error(f"Draft was not saved: {exc}")
        if st.button("Clear extracted request"):
            st.session_state.pop("email_request", None)
            for widget_key in [key for key in st.session_state if key.startswith("draft_body_")]:
                st.session_state.pop(widget_key, None)
            st.rerun()

elif page == "Offer draft review":
    st.subheader("Offer draft review")
    st.info("Offer exports are structured draft data only. No company template was provided; prices and commercial terms are never invented.")
    st.write("The clearance evaluation contains no proposed price/quantity until policy and approved price sources are configured.")
    if not inventory.empty:
        st.dataframe(inventory[[c for c in ("material_code", "description", "grade", "dimensions", "quantity_available", "reference_price", "minimum_approved_price", "currency", "source_file", "source_row", "validation_status") if c in inventory]], width="stretch")
        if st.button("Export offer-review dataset"):
            source_file = inventory.iloc[0].get("source_file") if "source_file" in inventory else None
            source_hash = st.session_state.get("last_import", {}).get("source_hash")
            source_run = repo.run_for_source(source_file, source_hash) if source_file else None
            run_id = source_run.get("run_id") if source_run else (latest.get("run_id") if latest else None)
            path = export_excel(inventory, ROOT / "data/output/offer_drafts/offer_review_dataset.xlsx", "Offer Review", run_id=run_id)
            repo.audit("OFFER_DATASET_EXPORTED", {"path": str(path.relative_to(ROOT))})
            st.success(f"Saved {path.relative_to(ROOT)}")

elif page == "Processing history":
    st.subheader("Processing history and audit")
    st.dataframe(pd.DataFrame(runs), width="stretch")
    with st.expander("Audit events"):
        st.dataframe(pd.DataFrame(repo.audit_events()), width="stretch")

else:
    st.subheader("Configuration and business rules")
    st.write("Resolved project root:", str(ROOT))
    st.write("Dry-run mode:", settings.get("app", {}).get("dry_run", True))
    st.write("Configured source aliases"); st.json(load_yaml("config/column_mappings.yaml", {}))
    st.write("Clearance rules (null means NOT_CONFIGURED)"); st.json(load_yaml("config/clearance_rules.yaml", {}))
    st.caption("Edit YAML in a text editor, then restart/refresh. Configuration changes are not automatically approved; review and back up changes.")
