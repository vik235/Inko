import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from server import create_app
import db

db.init_db()
c = create_app().test_client()

# Settings
c.post("/settings", data={
    "heading": "Payment Receipt",
    "business_name": "Vikas Gupta",
    "phone": "+91 99999 99999",
    "email": "vigupta@example.com",
    "address": "Bangalore, India",
    "default_currency": "INR",
    "currency_symbol": "Rs.",
    "footer": "Thank you for your payment.",
    "receipt_number_prefix": "R",
    "receipt_number_year_prefix": "1",
})

r = c.post("/api/receipts", data={
    "payer_name": "Aman Gupta",
    "amount": "28000",
    "currency": "INR",
    "receipt_date": "2026-04-28",
    "payment_method": "Bank transfer ****1234",
    "description": "Advance — voided/cancelled",
})
rid = r.headers["Location"].rsplit("/", 1)[-1]

# Void it
c.post(f"/receipts/{rid}/void")
rec = db.get_receipt(rid)
print(f"Voided receipt {rec['receipt_number']} -> {rec['pdf_path']}")
os.startfile(rec["pdf_path"])
