"""Email sending via SMTP (Gmail-friendly defaults).

`render_template_text` substitutes receipt + settings placeholders.
`send_via_smtp` connects to SMTP, attaches the PDF, and sends the message.
Raises EmailError with a friendly message on failure.
"""
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any


class EmailError(Exception):
    pass


PLACEHOLDER_KEYS = (
    "payer_name", "amount", "currency", "currency_symbol",
    "receipt_number", "receipt_date", "business_name", "id",
)


def render_template_text(template: str, receipt: dict[str, Any],
                          settings: dict[str, str]) -> str:
    if not template:
        return ""
    ctx: dict[str, Any] = {
        "payer_name": receipt.get("payer_name", ""),
        "amount": f"{float(receipt.get('amount', 0)):,.2f}",
        "currency": receipt.get("currency", ""),
        "currency_symbol": settings.get("currency_symbol", ""),
        "receipt_number": receipt.get("receipt_number") or receipt.get("id", ""),
        "receipt_date": receipt.get("receipt_date", ""),
        "business_name": settings.get("business_name", ""),
        "id": receipt.get("id", ""),
    }
    try:
        return template.format(**ctx)
    except KeyError as e:
        raise EmailError(f"Unknown placeholder in template: {e}")
    except (IndexError, ValueError) as e:
        raise EmailError(f"Invalid template syntax: {e}")


def send_via_smtp(
    to: str,
    subject: str,
    body: str,
    pdf_path: Path | None,
    settings: dict[str, str],
) -> None:
    if settings.get("smtp_enabled") != "1":
        raise EmailError("Email sending is not enabled in Settings.")

    host = (settings.get("smtp_host") or "smtp.gmail.com").strip()
    try:
        port = int(settings.get("smtp_port") or "465")
    except ValueError:
        raise EmailError("Invalid SMTP port.")
    user = (settings.get("smtp_username") or "").strip()
    password = settings.get("smtp_password") or ""
    if not user or not password:
        raise EmailError("Gmail address and app password are required (Settings).")
    if not to:
        raise EmailError("Recipient address is required.")
    if pdf_path is not None and not pdf_path.exists():
        raise EmailError(f"PDF not found: {pdf_path}")

    from_name = (settings.get("email_from_name") or settings.get("business_name") or user).strip()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{user}>" if from_name else user
    msg["To"] = to
    msg.set_content(body or "")

    if pdf_path is not None:
        with open(pdf_path, "rb") as fh:
            msg.add_attachment(
                fh.read(),
                maintype="application",
                subtype="pdf",
                filename=pdf_path.name,
            )

    ctx = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(user, password)
                s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise EmailError(
            "Gmail rejected the credentials. "
            "Use a 16-character App Password (myaccount.google.com/apppasswords), "
            "not your regular password."
        )
    except (smtplib.SMTPException, OSError) as e:
        raise EmailError(f"SMTP error: {e}")
