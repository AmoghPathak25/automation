from dataclasses import dataclass, field
from typing import Any
@dataclass
class ImportResult:
    run_id: str
    source_file: str
    source_sheet: str
    rows_read: int
    valid: int
    needs_review: int
    rejected: int
    records: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class EmailRequest:
    sender: str | None = None
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: str = ""
    category: str = "Unknown / manual review"
    customer_id: str | None = None
    material_code: str | None = None
    grade: str | None = None
    dimensions: str | None = None
    requested_quantity: float | None = None
    required_date: str | None = None
    mentioned_price: float | None = None
    currency: str | None = None
    requested_action: str | None = None
    confidence: str = "LOW"
    uncertainties: list[str] = field(default_factory=list)
