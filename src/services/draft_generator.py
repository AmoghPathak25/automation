from __future__ import annotations
from src.services.inventory_matcher import match_request

def generate_email_draft(request: dict, inventory, match_result: dict | None = None) -> dict:
    result = match_result or match_request(request, inventory)
    greeting = "Dear Sir/Madam,"
    if request.get("sender"):
        greeting = "Dear Customer,"
    lines = [greeting, "", "Thank you for your enquiry.", ""]
    if result["match_status"] == "EXACT_MATCH":
        lines.append("We have identified a corresponding inventory record for your requested product. Please note this is a draft for internal verification; availability is subject to a current stock check and approval.")
        row = result["matches"][0]
        if row.get("material_code"): lines.append(f"Material: {row['material_code']}")
        if row.get("quantity_available") not in (None, ""): lines.append(f"Reported available quantity: {row['quantity_available']} {row.get('unit_of_measure') or '(unit not specified)'}")
    elif result["match_status"] == "POSSIBLE_ALTERNATIVE":
        lines.append("We identified a possible alternative for review. It is not an exact material match and requires your technical/commercial confirmation before it is offered.")
    elif result["match_status"] == "NO_MATCH_FOUND":
        lines.append("We could not verify a matching item from the currently imported inventory. We will review and confirm separately.")
    else:
        lines.append("We need to confirm some product details before checking availability. Could you please clarify the material code, grade, dimensions, and requested quantity as applicable?")
    lines.extend(["", "Kind regards,", "[Use the existing company signature when sending]", "", "--- INTERNAL REVIEW ---", f"Match status: {result['match_status']}", f"Reason: {result['reason']}", "This message has NOT been sent. Verify stock freshness, recipient, specifications, price, and signature before use."])
    return {"status": "DRAFT", "approval_status": "PENDING_APPROVAL", "match_status": result["match_status"], "match_reason": result["reason"], "subject": request.get("subject", "Re: Product enquiry"), "to": request.get("sender"), "cc": request.get("cc", []), "body": "\n".join(lines), "send_enabled": False}
