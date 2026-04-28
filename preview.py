"""Generate a sample PDF with full settings + signature, and open it."""
import base64
import os
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from server import create_app
import db


def _fake_sig():
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
c.post("/settings", data={
    "heading": "Payment Receipt",
    "business_name": "Vikas Gupta",
    "phone": "+91 99999 99999",
    "email": "vigupta@example.com",
    "address": "Bangalore, India",
    "default_currency": "INR",
    "currency_symbol": "₹",
    "footer": "Thank you for your payment.",
    "receipt_number_prefix": "R",
    "receipt_number_year_prefix": "1",
    "signature_png": _fake_sig(),
})
r = c.post("/api/receipts", data={
    "payer_name": "Aman Gupta", "amount": "28000", "currency": "INR",
    "receipt_date": "2026-04-28",
    "payment_method": "Bank transfer ****1234",
    "description": "Advance",
})
rid = r.headers["Location"].rsplit("/", 1)[-1]
rec = db.get_receipt(rid)
print("Generated:", rec["receipt_number"])
print("PDF:", rec["pdf_path"])
os.startfile(rec["pdf_path"])
