"""Tests for the test-email endpoint and edit/void flows."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from server import create_app
import db
import smtplib


db.init_db()
c = create_app().test_client()

print("[1] /api/test-email with mocked SMTP -> ok=True, sent to self")
c.post("/settings", data={
    "business_name": "Test Co",
    "smtp_username": "test@gmail.com",
    "smtp_password": "app-pass-1234",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "465",
    "email_from_name": "Test",
    "smtp_enabled": "1",
})
with patch("emailer.smtplib.SMTP_SSL") as mock_smtp:
    inst = MagicMock()
    mock_smtp.return_value.__enter__.return_value = inst
    r = c.post("/api/test-email", data={})
assert r.status_code == 200, r.status_code
data = r.get_json()
assert data["ok"] is True, data
assert data["to"] == "test@gmail.com"
inst.login.assert_called_with("test@gmail.com", "app-pass-1234")
sent = inst.send_message.call_args[0][0]
assert sent["To"] == "test@gmail.com"
assert "SMTP test" in sent["Subject"]
# No attachment expected
assert len(list(sent.iter_attachments())) == 0
print("   OK - to:", data["to"])

print("[2] /api/test-email overrides saved values with form values")
with patch("emailer.smtplib.SMTP_SSL") as mock_smtp:
    inst = MagicMock()
    mock_smtp.return_value.__enter__.return_value = inst
    r = c.post("/api/test-email", data={
        "smtp_username": "other@gmail.com",
        "smtp_password": "different-pass",
    })
data = r.get_json()
assert data["ok"] is True
assert data["to"] == "other@gmail.com"
inst.login.assert_called_with("other@gmail.com", "different-pass")
print("   OK - form values used, sent to:", data["to"])

print("[3] /api/test-email surfaces auth errors as ok=False")
with patch("emailer.smtplib.SMTP_SSL") as mock_smtp:
    inst = MagicMock()
    inst.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad")
    mock_smtp.return_value.__enter__.return_value = inst
    r = c.post("/api/test-email", data={})
data = r.get_json()
assert r.status_code == 200
assert data["ok"] is False
assert "App Password" in data["error"]
print("   OK - error surfaced:", data["error"][:50] + "...")

print("[4] /api/test-email rejects empty username")
c.post("/settings", data={
    "business_name": "Test Co",
    "smtp_username": "",
    "smtp_password": "",
})
r = c.post("/api/test-email", data={})
assert r.status_code == 400
print("   OK - rejected with 400")

print()
print("--- Edit / Void tests ---")

# Reset settings + counters for deterministic numbering
with db.connect() as conn:
    conn.execute("DELETE FROM settings WHERE key LIKE 'receipt_counter%'")
c.post("/settings", data={
    "business_name": "Test Co", "currency_symbol": "Rs.",
    "default_currency": "INR",
    "receipt_number_prefix": "T",
})

print("[5] Create receipt -> get id")
r = c.post("/api/receipts", data={
    "payer_name": "Original Payer", "amount": "100.00",
    "currency": "INR", "receipt_date": "2026-04-28",
    "payment_method": "Cash", "description": "Original desc",
})
rid = r.headers["Location"].rsplit("/", 1)[-1]
rec = db.get_receipt(rid)
assert rec["payer_name"] == "Original Payer"
print("   id:", rid[-8:], "number:", rec["receipt_number"])

print("[6] GET /edit -> form pre-filled")
r = c.get(f"/receipts/{rid}/edit")
assert r.status_code == 200
body = r.data.decode("utf-8")
assert "Original Payer" in body
assert "100.00" in body
print("   OK")

print("[7] POST /edit -> updates fields, regenerates PDF")
r = c.post(f"/receipts/{rid}/edit", data={
    "payer_name": "Fixed Payer", "amount": "150.50",
    "currency": "INR", "receipt_date": "2026-04-28",
    "payment_method": "UPI", "description": "Fixed desc",
})
assert r.status_code == 302
rec2 = db.get_receipt(rid)
assert rec2["payer_name"] == "Fixed Payer", rec2["payer_name"]
assert rec2["amount"] == 150.50
assert rec2["payment_method"] == "UPI"
assert rec2["updated_at"], "updated_at not set"
# Receipt number must NOT change after edit
assert rec2["receipt_number"] == rec["receipt_number"]
print("   OK - payer/amount/method updated, number unchanged, updated_at set")

print("[8] POST /void -> marks voided, sets voided_at, PDF gets VOID watermark")
pdf_before = c.get(f"/receipts/{rid}/pdf").data
r = c.post(f"/receipts/{rid}/void")
assert r.status_code == 302
rec3 = db.get_receipt(rid)
assert rec3["voided"] == 1
assert rec3["voided_at"]
pdf_after = c.get(f"/receipts/{rid}/pdf").data
assert pdf_after != pdf_before, "PDF unchanged after voiding (watermark missing?)"
print(f"   OK - voided at {rec3['voided_at']}, PDF size {len(pdf_before)}->{len(pdf_after)}")

print("[9] Voided receipt: GET /edit redirects (no editing voided receipts)")
r = c.get(f"/receipts/{rid}/edit", follow_redirects=False)
assert r.status_code == 302, r.status_code
assert f"/receipts/{rid}" in r.headers["Location"]
print("   OK - redirected away")

print("[10] POST /unvoid -> restores")
r = c.post(f"/receipts/{rid}/unvoid")
assert r.status_code == 302
rec4 = db.get_receipt(rid)
assert rec4["voided"] == 0
assert rec4["voided_at"] is None
print("   OK")

print("[11] After unvoid: editing works again")
r = c.post(f"/receipts/{rid}/edit", data={
    "payer_name": "Final Payer", "amount": "200",
    "currency": "INR", "receipt_date": "2026-04-28",
})
assert r.status_code == 302
assert db.get_receipt(rid)["payer_name"] == "Final Payer"
print("   OK")

print("[12] History page renders voided rows correctly")
# Re-void
c.post(f"/receipts/{rid}/void")
r = c.get("/history")
assert r.status_code == 200
body = r.data.decode("utf-8")
assert "voided-row" in body
assert "VOID" in body
print("   OK")

print()
print("All checks passed.")
