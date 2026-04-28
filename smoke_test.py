"""Smoke test - signatures + email flow with mocked smtplib."""
import base64
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from server import create_app
import db


def _fake_sig() -> str:
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (220, 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(10, 50), (40, 20), (75, 50), (105, 25), (140, 50),
            (170, 30), (200, 50)], fill=(15, 23, 42, 255), width=3)
    buf = BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


db.init_db()
with db.connect() as conn:
    conn.execute("DELETE FROM settings WHERE key LIKE 'receipt_counter%'")

c = create_app().test_client()

print("[1/8] Save full settings (signature + Gmail SMTP enabled)")
form = {
    "heading": "Payment Receipt",
    "business_name": "Vikas Gupta",
    "phone": "+91 99999 99999",
    "email": "vigupta@example.com",
    "address": "Bangalore, India",
    "default_currency": "INR",
    "currency_symbol": "Rs.",
    "footer": "Thank you for your payment.",
    "receipt_number_prefix": "R",
    "receipt_number_year_prefix": "",
    "signature_png": _fake_sig(),
    "smtp_enabled": "1",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "465",
    "smtp_username": "test@gmail.com",
    "smtp_password": "app-password-1234",
    "email_from_name": "Vikas",
    "email_subject_template": "Receipt {receipt_number} from {business_name}",
    "email_body_template": "Hi {payer_name},\nReceipt {receipt_number} for {currency_symbol}{amount}.",
}
r = c.post("/settings", data=form)
assert r.status_code in (200, 302)
s = db.get_settings()
assert s["smtp_enabled"] == "1"
assert s["smtp_username"] == "test@gmail.com"
print("   OK")

print("[2/8] Create receipt with payer email")
r = c.post("/api/receipts", data={
    "payer_name": "Aman Gupta", "amount": "28000", "currency": "INR",
    "receipt_date": "2026-04-28", "payment_method": "UPI",
    "description": "Advance", "email_address": "aman@example.com",
})
rid = r.headers["Location"].rsplit("/", 1)[-1]
rec = db.get_receipt(rid)
print("   number:", rec["receipt_number"])
print("   email_status:", rec["email_status"])

print("[3/8] GET compose page - should pre-fill from templates")
r = c.get(f"/receipts/{rid}/email")
assert r.status_code == 200
body = r.data.decode("utf-8")
assert "aman@example.com" in body
assert "Receipt R-00001" in body, "subject template not rendered"
assert "Aman Gupta" in body, "body template not rendered"
print("   OK - subject + body rendered with placeholders")

print("[4/8] POST send with mocked SMTP_SSL -> success")
with patch("emailer.smtplib.SMTP_SSL") as mock_smtp:
    inst = MagicMock()
    mock_smtp.return_value.__enter__.return_value = inst
    r = c.post(f"/receipts/{rid}/email", data={
        "to": "aman@example.com",
        "subject": "Receipt R-00001 from Vikas Gupta",
        "body": "Hi Aman,\nThanks!",
    })
assert r.status_code == 302, f"expected redirect, got {r.status_code}"
assert mock_smtp.called, "smtplib.SMTP_SSL not invoked"
inst.login.assert_called_with("test@gmail.com", "app-password-1234")
inst.send_message.assert_called_once()
sent_msg = inst.send_message.call_args[0][0]
assert sent_msg["To"] == "aman@example.com"
assert "R-00001" in sent_msg["Subject"]
# Verify the PDF attachment is present
attached = list(sent_msg.iter_attachments())
assert len(attached) == 1, f"expected 1 attachment, got {len(attached)}"
att = attached[0]
assert att.get_content_type() == "application/pdf"
pdf_bytes = att.get_payload(decode=True)
assert pdf_bytes[:4] == b"%PDF", "attachment is not a PDF"
print(f"   OK - PDF attached ({len(pdf_bytes)} bytes)")

assert db.get_receipt(rid)["email_status"] == "sent"
print("   email_status: sent")

print("[5/8] POST send -> SMTP auth error surfaces nicely")
import smtplib
with patch("emailer.smtplib.SMTP_SSL") as mock_smtp:
    inst = MagicMock()
    inst.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad creds")
    mock_smtp.return_value.__enter__.return_value = inst
    r = c.post(f"/receipts/{rid}/email", data={
        "to": "aman@example.com", "subject": "x", "body": "y",
    })
assert r.status_code == 200
body = r.data.decode("utf-8")
assert "App Password" in body, "auth error message missing"
print("   OK - shows guidance about App Password")
assert db.get_receipt(rid)["email_status"] == "failed"
print("   email_status: failed")

print("[6/8] Settings page renders with new email fields")
r = c.get("/settings")
assert r.status_code == 200
b = r.data.decode("utf-8")
for needle in ("smtp_enabled", "smtp_username", "Subject template",
               "Body template", "data-tab=\"type\"", "signature-pad.js"):
    assert needle in b, f"missing in settings: {needle}"
# Font list is populated by the JS asset
js = c.get("/static/signature-pad.js").data.decode("utf-8")
for f in ("Caveat", "Dancing Script", "Great Vibes", "Sacramento"):
    assert f in js, f"font missing from JS: {f}"
print("   OK")

print("[7/8] Static font files served")
for f in ["Caveat-Regular.ttf", "DancingScript-Regular.ttf",
          "GreatVibes-Regular.ttf", "Sacramento-Regular.ttf"]:
    r = c.get(f"/static/fonts/{f}")
    assert r.status_code == 200, f"{f} not served: {r.status_code}"
    assert r.data[:4] == b"\x00\x01\x00\x00", f"{f} not TTF"
print("   OK")

print("[8/8] PDF embeds the saved signature")
pdf_path = Path(rec["pdf_path"])
assert pdf_path.exists()
size = pdf_path.stat().st_size
assert size > 70_000, f"PDF too small ({size}); signature may not be embedded"
print(f"   OK - PDF size: {size} bytes")

print()
print("All checks passed.")
