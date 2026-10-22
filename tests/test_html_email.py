from email.message import EmailMessage
from src.services.email_classifier import parse_eml

def make_email(path, html, plain=None):
    message = EmailMessage()
    message["From"] = "synthetic@example.invalid"
    message["To"] = "review@example.invalid"
    message["Subject"] = "Synthetic availability enquiry"
    if plain is not None:
        message.set_content(plain)
        message.add_alternative(html, subtype="html")
    else:
        message.set_content(html, subtype="html")
    path.write_bytes(message.as_bytes())
    return path

def test_html_only_eml_is_converted_without_executing_markup(tmp_path):
    path = make_email(tmp_path / "html_only.eml", "<html><body><p>Availability request for material: SYN001</p><script>alert('never run')</script><img src='https://example.invalid/tracker'></body></html>")
    result = parse_eml(path)
    assert "Availability request for material: SYN001" in result["source_text"]
    assert "alert" not in result["source_text"]
    assert "tracker" not in result["source_text"]
    assert result["html_converted"] is True
    assert any("HTML-only" in warning for warning in result["uncertainties"])

def test_plain_text_is_preferred_when_both_parts_exist(tmp_path):
    path = make_email(tmp_path / "multipart.eml", "<p>HTML alternative</p>", "Plain body should be preferred.")
    result = parse_eml(path)
    assert "Plain body should be preferred." in result["source_text"]
    assert "HTML alternative" not in result["source_text"]
    assert result["html_converted"] is False
