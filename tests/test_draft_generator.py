from src.services.draft_generator import generate_email_draft
from src.services.inventory_matcher import match_request

def test_draft_not_sent_and_explicit_match_status():
    inventory = [{"material_code": "A", "grade": "G", "dimensions": "10mm", "quantity_available": "2", "validation_status": "VALIDATED"}]
    request = {"sender": "customer@example.invalid", "subject": "Stock enquiry", "material_code": "A", "grade": "G", "dimensions": "10mm", "requested_quantity": 1}
    result = match_request(request, inventory)
    draft = generate_email_draft(request, inventory, result)
    assert draft["match_status"] == "EXACT_MATCH"
    assert draft["send_enabled"] is False
    assert "NOT been sent" in draft["body"]
    assert "quantity: 2" in draft["body"]

def test_missing_information_does_not_create_approval_ready_offer():
    from src.services.clearance_engine import calculate_offer_price
    result = calculate_offer_price(None, None, None, None, None)
    assert result["approval_ready"] is False
