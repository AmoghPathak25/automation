from __future__ import annotations
from pathlib import Path
from pypdf import PdfReader
from src.utils.file_safety import validate_file

def extract_pdf_text(path: str | Path) -> dict:
    source = Path(path)
    validate_file(source)
    if source.suffix.lower() != ".pdf":
        raise ValueError("Expected a .pdf file.")
    try:
        reader = PdfReader(str(source), strict=False)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        return {"status": "REJECT", "text": "", "pages": 0, "message": f"PDF unreadable: {type(exc).__name__}"}
    text = "\n\n".join(item for item in pages if item)
    if not text.strip():
        return {"status": "NEEDS_REVIEW", "text": "", "pages": len(pages), "message": "No selectable text found; this may be a scanned PDF. OCR is not configured."}
    return {"status": "VALIDATED", "text": text, "pages": len(pages), "message": "Text extracted; verify extraction against the source PDF."}
