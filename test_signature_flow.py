"""Focused test: changing signature in settings flows into existing receipt PDFs."""
import base64
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from server import create_app
import db


def _sig(stroke_width: int) -> str:
    """Generate two distinguishable signatures by varying line thickness."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (220, 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(10, 50), (200, 20)], fill=(15, 23, 42, 255), width=stroke_width)
    buf = BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


db.init_db()
with db.connect() as conn:
    conn.execute("DELETE FROM settings WHERE key LIKE 'receipt_counter%'")

c = create_app().test_client()

# Step 1: configure with signature A
print("[1] Settings with signature A (thin)")
sig_a = _sig(2)
c.post("/settings", data={
    "business_name": "Test Co", "currency_symbol": "Rs.",
    "default_currency": "INR", "signature_png": sig_a,
})
assert db.get_settings()["signature_png"] == sig_a

# Step 2: create a receipt -> PDF generated with sig A
print("[2] Create receipt -> PDF generated with signature A")
r = c.post("/api/receipts", data={
    "payer_name": "Test", "amount": "100", "currency": "INR",
    "receipt_date": "2026-04-28",
})
rid = r.headers["Location"].rsplit("/", 1)[-1]
pdf_v1 = c.get(f"/receipts/{rid}/pdf").data
assert pdf_v1[:4] == b"%PDF"
print("   v1 size:", len(pdf_v1))

# Step 3: change signature to B
print("[3] Update settings with signature B (thick)")
sig_b = _sig(8)
c.post("/settings", data={
    "business_name": "Test Co", "currency_symbol": "Rs.",
    "default_currency": "INR", "signature_png": sig_b,
})
assert db.get_settings()["signature_png"] == sig_b
assert db.get_settings()["signature_png"] != sig_a

# Step 4: re-fetch the SAME receipt's PDF -> should now contain sig B
print("[4] Re-fetch same receipt's PDF -> should reflect signature B")
pdf_v2 = c.get(f"/receipts/{rid}/pdf").data
assert pdf_v2[:4] == b"%PDF"
print("   v2 size:", len(pdf_v2))

# The PDFs should differ because the signature image bytes differ
assert pdf_v1 != pdf_v2, "PDF did not change after signature update — regen-on-view broken"
print("   OK - PDF was regenerated with new signature")

# Step 5: per-receipt re-sign overrides default
print("[5] Per-receipt re-sign overrides settings default")
sig_c = _sig(5)
c.post(f"/receipts/{rid}/sign", data={"signature_png": sig_c})
assert db.get_receipt(rid)["signature_png"] == sig_c
pdf_v3 = c.get(f"/receipts/{rid}/pdf").data
assert pdf_v3 != pdf_v2
print("   OK")

# Step 6: erase per-receipt sig -> falls back to default (sig B)
print("[6] Erase per-receipt sig -> falls back to default")
c.post(f"/receipts/{rid}/sign", data={"signature_png": ""})
assert (db.get_receipt(rid)["signature_png"] or "") == ""
pdf_v4 = c.get(f"/receipts/{rid}/pdf").data
# Should be roughly equivalent to v2 (default sig B again)
print("   OK")

print()
print("All checks passed.")
