import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from paths import db_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id TEXT PRIMARY KEY,
    receipt_number TEXT,
    created_at TEXT NOT NULL,
    receipt_date TEXT NOT NULL,
    payer_name TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    payment_method TEXT,
    description TEXT,
    pdf_path TEXT,
    email_status TEXT NOT NULL DEFAULT 'none',
    email_address TEXT,
    signature_png TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(receipts)").fetchall()}
        for col, ddl in [
            ("receipt_number", "ALTER TABLE receipts ADD COLUMN receipt_number TEXT"),
            ("signature_png",  "ALTER TABLE receipts ADD COLUMN signature_png TEXT"),
        ]:
            if col not in cols:
                conn.execute(ddl)


# ---------- settings ----------

DEFAULT_SETTINGS: dict[str, str] = {
    "heading": "Payment Receipt",
    "business_name": "",
    "address": "",
    "phone": "",
    "email": "",
    "footer": "Thank you for your payment.",
    "default_currency": "INR",
    "currency_symbol": "₹",
    "receipt_number_prefix": "",
    "receipt_number_year_prefix": "0",
    "signature_png": "",
    # Email (Gmail SMTP)
    "smtp_enabled": "0",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "465",
    "smtp_username": "",
    "smtp_password": "",
    "email_from_name": "",
    "email_subject_template": "Receipt {receipt_number} from {business_name}",
    "email_body_template": (
        "Hi {payer_name},\n\n"
        "Please find attached the receipt {receipt_number} for {currency_symbol}{amount} "
        "received on {receipt_date}.\n\n"
        "Thanks,\n{business_name}"
    ),
}

# Keys that aren't user-editable from the form (managed internally)
INTERNAL_KEYS = {"receipt_counter"}


def get_settings() -> dict[str, str]:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    stored = {r["key"]: r["value"] for r in rows}
    return {**DEFAULT_SETTINGS, **stored}


def save_settings(values: dict[str, Any]) -> None:
    with connect() as conn:
        for key in DEFAULT_SETTINGS:
            if key not in values:
                continue
            val = values.get(key, "")
            if val is None:
                val = ""
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(val)),
            )


def _get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def _set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


# ---------- receipt numbering ----------

def next_receipt_number() -> str:
    """Allocate the next display number, e.g. '00001', 'R-00001', '2026-00001'.

    Uses a counter stored in the settings table. Counter is global, or
    per-year when year-prefix is enabled.
    """
    with connect() as conn:
        prefix = _get_setting(conn, "receipt_number_prefix", "").strip()
        year_prefix = _get_setting(conn, "receipt_number_year_prefix", "0") == "1"

        year = datetime.now().year
        counter_key = f"receipt_counter_{year}" if year_prefix else "receipt_counter"
        n = int(_get_setting(conn, counter_key, "0") or "0") + 1
        _set_setting(conn, counter_key, str(n))

    parts: list[str] = []
    if prefix:
        parts.append(prefix)
    if year_prefix:
        parts.append(str(year))
    parts.append(f"{n:05d}")
    return "-".join(parts)


# ---------- receipts ----------

def insert_receipt(r: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO receipts
               (id, receipt_number, created_at, receipt_date, payer_name, amount,
                currency, payment_method, description, pdf_path, email_status,
                email_address, signature_png)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r["id"], r.get("receipt_number"), r["created_at"], r["receipt_date"],
                r["payer_name"], r["amount"], r["currency"],
                r.get("payment_method", ""), r.get("description", ""),
                r.get("pdf_path", ""), r.get("email_status", "none"),
                r.get("email_address", ""), r.get("signature_png", ""),
            ),
        )


def list_receipts(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM receipts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_receipt(receipt_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
    return dict(row) if row else None


def update_pdf_path(receipt_id: str, pdf_path: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE receipts SET pdf_path = ? WHERE id = ?", (pdf_path, receipt_id)
        )


def update_signature(receipt_id: str, signature_png: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE receipts SET signature_png = ? WHERE id = ?",
            (signature_png, receipt_id),
        )


def update_email_status(receipt_id: str, status: str, address: str | None = None) -> None:
    with connect() as conn:
        if address is not None:
            conn.execute(
                "UPDATE receipts SET email_status = ?, email_address = ? WHERE id = ?",
                (status, address, receipt_id),
            )
        else:
            conn.execute(
                "UPDATE receipts SET email_status = ? WHERE id = ?",
                (status, receipt_id),
            )


def display_number(r: dict[str, Any]) -> str:
    """Return the human-readable number for a receipt, falling back to id tail."""
    return r.get("receipt_number") or r["id"][-8:]
