# Office Email Automation
A local-first Windows dashboard for turning manually collected SAP Excel exports and saved business correspondence into traceable, reviewable data. It does **not** connect to SAP, log into email, send messages, use external AI, or make commercial decisions.

## What was actually available at implementation
The verified project directory initially contained only an empty file named `sap`. No recordings, workbooks, PDFs, email examples, offer templates, or company-specific policy files were present. Therefore source schemas, exact SAP aliases, business units/currencies, stock-age definitions, customer eligibility, pricing policy, branding/signature, and offer format remain unknown. The starter alias map is a configurable set of common column labels, not a claim about your SAP export. Clearance thresholds are intentionally `null` in `config/clearance_rules.yaml`.

The environment initially had Python 3.10.11 and none of the required packages installed. Python 3.11+ is recommended (the code uses Python 3.10-compatible syntax); Python 3.10 may also work with compatible dependency versions.

## Features
- Streamlit local dashboard with overview, import/preview, validation, inventory search, clearance evaluation, email request review, offer-data export, processing history, and rule inspection.
- Excel `.xlsx` / `.xlsm` (read-only values; macros are never executed), CSV, text-based PDF extraction, `.txt`, and `.eml` parsing. Plain-text EML bodies are preferred; an HTML-only body is converted to readable text without executing markup/scripts or fetching content and is flagged for manual review. `.msg` is unsupported. Excel worksheets are selectable.
- Configurable source-column aliases; raw source values and source file/sheet/row are retained. Text material identifiers are preserved, including leading zeros. If Excel stored a material code as a number, zeros already lost upstream cannot be restored and the record warns for review.
- Deterministic validation for required identifiers, duplicate keys, negative/unparseable quantities, price consistency/currency, dates, stale stock exports when configured, and input issues. Duplicate rows are not aggregated.
- Clearance reasons are rule-driven. Unset rules are explicitly reported and cannot generate candidates or price suggestions. There is no inferred commercial policy.
- Local SQLite history, duplicate import protection (same file hash + worksheet), audit events, atomic report writes, timestamped validation/clearance/offer-review Excel and CSV exports (with run ID when available), and structured offer-review Excel export. Export filenames use `YYYYMMDD_HHMMSS_microseconds` and an optional sanitized run ID; collisions add a numeric suffix instead of overwriting. Upload staging uses a separate randomized temporary directory per file and cleans it after processing.
- Manual email parsing with uncertainty indicators, exact-vs-alternative matching, and unsent draft preparation. No external AI dependency is used. Ollama/Qwen is not implemented in this milestone; all workflows remain available without it.

## Installation (Windows PowerShell)

From this project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process Bypass` in that window, or invoke `.venv\Scripts\python.exe` directly. Launch with:

```powershell
python -m src
```

or `streamlit run src/app.py`. The browser UI is hosted locally by Streamlit. Do not expose its port to an untrusted network.

Run tests:

```powershell
python -m pytest -q
```

## First-use workflow
1. Review `config/column_mappings.yaml`; add aliases based on an anonymized actual export. Do not map a field to a similarly named but semantically different SAP field.
2. Review `config/settings.yaml`, especially required fields, duplicate-key fields, optional stock-export freshness limit, and `app.date_format`. The default date format is `%Y-%m-%d` (for example `2026-02-01`); set it to the exact unambiguous format used by your export (e.g. `%d/%m/%Y`). Text dates that do not strictly match it require review. If the setting is removed/set to null, only exact ISO dates are accepted; ambiguous dates such as `01/02/2026` are never guessed.
3. Obtain and approve business rules before changing `config/clearance_rules.yaml`; no thresholds are supplied by default. An ageing threshold alone does not establish excess stock.
4. In **Import files**, select a workbook/CSV and inspect its preview and worksheet. Import explicitly to normalize, validate, and add a processing run. If a workbook is macro-enabled, macros remain inert; formulas are read as cached values where available.
5. Review **Validation report**. Investigate every NEEDS_REVIEW/rejected row and confirm normalized values against the source. Export reports from the dashboard as needed.
6. Use **Clearance candidates** only after configuring the rules. The evaluator excludes invalid inventory and reports missing rule configuration. Price and proposed quantity remain blank; no customer suitability is inferred.
7. Paste or upload a saved `.eml`/`.txt` enquiry under **Import files**, or paste content in **Email request review**. Check extracted fields, match status, stock freshness, and source details; edit the proposed wording and save an unsent draft. Never treat POSSIBLE_ALTERNATIVE as an exact match. Saving subsequent edits updates the existing draft ID.
8. Back up the database/configuration and protect local business data. Source files are never changed; each dashboard upload is staged under a collision-resistant temporary folder and cleaned up when processing completes or fails.
9. Validate importer mappings and export behavior against synthetic tests, then check all assumptions against an anonymized actual SAP workbook before operational use.

## Data and security
- SQLite runtime data: `data/working/automation.sqlite3` (gitignored and excluded from synchronization by `.gitignore`). Protect/backup it as sensitive business data.
- Generated reports: `data/output/`. Input, working, archive, outputs, logs, database files, secrets, and Python caches are excluded from Git; OneDrive may still synchronize locally created runtime files according to its folder settings. For highly sensitive data, choose a properly protected local storage location and adjust storage configuration before use.
- `data/input/` is available for local organization; the dashboard upload stages an independent copy for parsing. Imported source paths and row numbers are retained in normalized records. Timestamped report exports are saved as new files, optionally suffixed with the associated run ID; if a generated name already exists, a numbered suffix is used rather than replacing the older report.
- No source content or customer data is written to logs. The UI displays local source names and extracted business data to the local user.
- Never place secrets in YAML. Email and attachment text is untrusted data and is not treated as executable instructions.
- Database duplicate protection uses source SHA-256 + sheet; changing a file creates a new run. Imports are not silently replaced.

## Configuration notes
- `column_mappings.yaml`: canonical field keys to recognized source header aliases. Normalization preserves raw source values in `original_values` and does not convert unknown units/currencies.
- `settings.yaml`: local paths, upload limit, required fields, duplicate key, stale threshold, and strict `app.date_format` used for text stock/movement dates and clearance ageing calculations.
- `clearance_rules.yaml`: intentionally unset business rules. Configure only with documented approval. Export candidate status is not equivalent to approval.
- No company offer template was supplied; offer export is a structured review dataset, not a branded offer.

## Known limitations
- No live SAP/browser/email/WhatsApp integration, authenticated automation, message sending, OCR, `.msg` parser, actual company-specific alias validation, approved pricing list/customer list ingestion workflow, template population, or Ollama integration.
- Price/customer reference files can be imported and normalized using available aliases, but this release does not automatically merge reference tables into validated commercial decisions. Currency compatibility across files is consequently not confirmed automatically.
- Text dates must match the configured `app.date_format`; if it is unset, only exact ISO `YYYY-MM-DD` dates are accepted. Excel-native date cells are treated as dates and preserved. Confirm SAP export date semantics against an anonymized workbook.
- Matching is conservative and exact on explicitly supplied material/specification fields; similar products require human review. Stock availability is only as reliable/fresh as the imported validated file.
- HTML-only `.eml` bodies are parsed to visible text with scripts/styles/embedded active content ignored. No HTML is executed and no external content is fetched. Converted bodies carry an uncertainty warning; check rendered intent manually. Attachments are listed but not auto-extracted or opened.

## Troubleshooting
- **Workbook parse error:** open a copy in Excel and save as `.xlsx`; never enable/execute macros. Check worksheet and header row structure.
- **Unexpected unmapped fields:** inspect actual headers, add safe aliases, rerun import; do not alter the source export.
- **Leading-zero warning:** request SAP export as text or set the code column to text before export. Formatting a numeric cell after zeros were lost does not restore them.
- **All clearance rows NOT_CONFIGURED:** expected until required commercial rules are supplied and approved.
- **PDF needs review:** scanned/image-only PDF requires a separately approved local OCR component; none is configured.
- **Port already in use:** run `python -m streamlit run src/app.py --server.port 8502`.
- **Database/report backup:** stop the app, then copy `data/working/automation.sqlite3`, `config/`, and required outputs to approved protected storage.

## Acceptance checklist
- [x] Windows-oriented local Streamlit application and configurable paths.
- [x] Excel/CSV preview/import, selectable sheets, source traceability, normalization and validation (synthetic regression coverage only; not yet verified on actual SAP exports).
- [x] Local PDF text extraction and OCR-needed state for image-only PDFs.
- [x] SQLite processing/audit history and repeat-import protection.
- [x] Rule-driven clearance status, explainability, and safe default-unconfigured policy.
- [x] Manual email text/EML review, conservative matching, unsent drafts.
- [x] Excel/CSV reports and synthetic automated tests.
- [ ] Validate mappings, date semantics, preview/import/export behavior against an anonymized real SAP export; synthetic workbook tests do not prove production SAP compatibility.
- [ ] Populate clearance/pricing policy from authorized business rules.
- [ ] Validate with real approved price/customer lists and an actual offer template.
- [ ] Verify installation/UI startup in Python 3.11+ on the target Windows desktop.
