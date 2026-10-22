from __future__ import annotations
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from html.parser import HTMLParser
from pathlib import Path
import re
from src.database.models import EmailRequest
from src.utils.file_safety import validate_file
class _SafeHTMLText(HTMLParser):
    # Extract visible text without executing markup or loading remote content.
    _IGNORED = {"script", "style", "noscript", "head", "iframe", "object", "svg"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignore_depth = 0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._IGNORED:
            self.ignore_depth += 1
        elif not self.ignore_depth and tag.lower() in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag.lower() in self._IGNORED and self.ignore_depth:
            self.ignore_depth -= 1
        elif not self.ignore_depth and tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.ignore_depth:
            self.parts.append(data)
    def text(self) -> str:
        return re.sub(r"[ \t]+", " ", "".join(self.parts)).strip()

def _html_to_plain_text(content: str) -> str:
    parser = _SafeHTMLText()
    parser.feed(content)
    parser.close()
    return parser.text()

KEYWORDS = {
    "Product availability enquiry": ("available", "availability", "in stock", "stock"),
    "Product specification enquiry": ("specification", "specs", "grade", "dimension", "size"),
    "Alternative-product request": ("alternative", "equivalent", "substitute"),
    "Stock-clearance opportunity": ("clearance", "offer", "discount", "slow moving"),
    "Sales-order-related request": ("sales order", "purchase order", "order number", "po number"),
    "Dispatch or delivery communication": ("dispatch", "delivery", "shipment", "tracking"),
    "Receipt or reconciliation issue": ("received", "reconciliation", "invoice mismatch", "short received"),
}

def parse_email_text(text: str) -> dict:
    headers, body = {}, text
    if "\n\n" in text:
        header_text, body = text.replace("\r\n", "\n").split("\n\n", 1)
        for line in header_text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1); headers[key.strip().lower()] = value.strip()
    normalized = body.casefold()
    scores = {category: sum(1 for word in words if word in normalized) for category, words in KEYWORDS.items()}
    if len(headers) < 2:
        return {"sender": None, "recipients": [], "cc": [], "subject": "", "category": "Unknown / manual review", "customer_id": None, "material_code": None, "grade": None, "dimensions": None, "requested_quantity": None, "required_date": None, "mentioned_price": None, "currency": None, "requested_action": None, "confidence": "LOW", "uncertainties": ["Email headers are malformed or absent; review manually."], "source_text": body}
    best = max(scores.values(), default=0)
    winners = [category for category, score in scores.items() if score == best and score > 0]
    category = winners[0] if len(winners) == 1 else "Unknown / manual review"
    code = re.search(r"\b(?:material|mat(?:erial)?\s*(?:code|no)?|sku|item)\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9_-]{1,})\b", body, re.I)
    quantity = re.search(r"\b(?:qty|quantity)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\b", body, re.I)
    grade = re.search(r"\bgrade\s*[:=]?\s*([^,;\n]+)", body, re.I)
    dimension = re.search(r"\b(?:dimensions?|size)\s*[:=]?\s*([^,;\n]+)", body, re.I)
    uncertainties = []
    if not code: uncertainties.append("Material code not explicitly identified.")
    if not quantity: uncertainties.append("Requested quantity not explicitly identified.")
    return {"sender": headers.get("from"), "recipients": [x for _, x in getaddresses([headers.get("to", "")]) if x], "cc": [x for _, x in getaddresses([headers.get("cc", "")]) if x],
            "subject": headers.get("subject", ""), "category": category, "customer_id": None,
            "material_code": code.group(1) if code else None, "grade": grade.group(1).strip() if grade else None,
            "dimensions": dimension.group(1).strip() if dimension else None, "requested_quantity": float(quantity.group(1)) if quantity else None,
            "required_date": None, "mentioned_price": None, "currency": None, "requested_action": None,
            "confidence": "MEDIUM" if code and (grade or dimension) else "LOW", "uncertainties": uncertainties, "source_text": body}

def parse_eml(path: str | Path) -> dict:
    source = Path(path)
    validate_file(source)
    if source.suffix.lower() != ".eml": raise ValueError("Only .eml email files are supported; .msg is not supported.")
    try:
        with source.open("rb") as stream: message = BytesParser(policy=policy.default).parse(stream)
        plain_body = message.get_body(preferencelist=("plain",))
        converted_from_html = plain_body is None
        if plain_body is not None:
            content = plain_body.get_content()
        else:
            html_body = message.get_body(preferencelist=("html",))
            if html_body is None and message.get_content_type() == "text/html":
                html_body = message
            content = _html_to_plain_text(html_body.get_content()) if html_body is not None else ""
        text = "\n".join(f"{key}: {message.get(key)}" for key in ("From", "To", "Cc", "Subject") if message.get(key)) + "\n\n" + content
        result = parse_email_text(text)
        if converted_from_html:
            result["uncertainties"].append("HTML-only message body was converted to plain text; verify the extracted wording manually.")
            result["html_converted"] = True
        else:
            result["html_converted"] = False
        result["attachment_references"] = [part.get_filename() for part in message.iter_attachments() if part.get_filename()]
        return result
    except Exception as exc:
        return {"sender": None, "recipients": [], "cc": [], "subject": "", "category": "Unknown / manual review", "material_code": None, "confidence": "LOW", "uncertainties": [f"Malformed email data ({type(exc).__name__}); review manually."], "attachment_references": []}
