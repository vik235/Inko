from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask, abort, jsonify, redirect, render_template, request, send_file, url_for,
)
from ulid import ULID

import db
from emailer import EmailError, render_template_text, send_via_smtp
from paths import pdf_output_dir, resource_path
from pdf_gen import generate_receipt_pdf


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(resource_path("templates")),
        static_folder=str(resource_path("static")),
    )
    # Allow large form posts (signature data URLs can be 50–200 KB)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    db.init_db()

    def _regen_pdf(receipt_id: str) -> Path:
        r = db.get_receipt(receipt_id)
        assert r is not None
        pdf_path = generate_receipt_pdf(r, db.get_settings())
        db.update_pdf_path(receipt_id, str(pdf_path))
        return pdf_path

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            settings=db.get_settings(),
            today=datetime.now().date().isoformat(),
        )

    @app.route("/history")
    def history():
        receipts = db.list_receipts()
        for r in receipts:
            r["display_number"] = db.display_number(r)
        return render_template(
            "history.html", receipts=receipts, settings=db.get_settings(),
        )

    @app.route("/settings", methods=["GET", "POST"])
    def settings_page():
        if request.method == "POST":
            db.save_settings(request.form.to_dict())
            return redirect(url_for("settings_page", saved="1"))
        return render_template(
            "settings.html",
            settings=db.get_settings(),
            saved=request.args.get("saved") == "1",
        )

    @app.route("/api/receipts", methods=["POST"])
    def create_receipt():
        form = request.form
        try:
            amount = float(form.get("amount", "0") or 0)
        except ValueError:
            return jsonify({"error": "Invalid amount"}), 400
        if not form.get("payer_name"):
            return jsonify({"error": "Payer name required"}), 400
        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0"}), 400

        settings = db.get_settings()
        currency = form.get("currency") or settings.get("default_currency", "INR")

        receipt = {
            "id": str(ULID()),
            "receipt_number": db.next_receipt_number(),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "receipt_date": form.get("receipt_date") or datetime.now().date().isoformat(),
            "payer_name": form.get("payer_name", "").strip(),
            "amount": amount,
            "currency": currency,
            "payment_method": form.get("payment_method", "").strip(),
            "description": form.get("description", "").strip(),
            "email_status": "none",
            "email_address": form.get("email_address", "").strip(),
            "signature_png": "",
        }
        db.insert_receipt(receipt)
        pdf_path = generate_receipt_pdf(receipt, settings)
        db.update_pdf_path(receipt["id"], str(pdf_path))
        return redirect(url_for("receipt_view", receipt_id=receipt["id"]))

    @app.route("/receipts/<receipt_id>")
    def receipt_view(receipt_id: str):
        r = db.get_receipt(receipt_id)
        if not r:
            abort(404)
        r["display_number"] = db.display_number(r)
        # Always include a cache-bust so the iframe re-fetches after settings
        # changes that happened in between page views.
        bust = request.args.get("v") or datetime.now().strftime("%Y%m%d%H%M%S%f")
        return render_template(
            "receipt_view.html",
            receipt=r,
            settings=db.get_settings(),
            cache_bust=bust,
        )

    @app.route("/receipts/<receipt_id>/pdf")
    def receipt_pdf(receipt_id: str):
        r = db.get_receipt(receipt_id)
        if not r:
            abort(404)
        # Always regenerate so updates to settings (signature, header, brand,
        # currency) flow into existing receipts the next time they're viewed.
        pdf_path = _regen_pdf(receipt_id)
        resp = send_file(
            str(pdf_path),
            mimetype="application/pdf",
            as_attachment=request.args.get("download") == "1",
            download_name=pdf_path.name,
        )
        # WebView2 / Chromium aggressively caches PDF iframes by URL. Force fresh.
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.route("/receipts/<receipt_id>/sign", methods=["POST"])
    def receipt_sign(receipt_id: str):
        r = db.get_receipt(receipt_id)
        if not r:
            abort(404)
        sig = request.form.get("signature_png", "")
        if sig and not sig.startswith("data:image/"):
            return jsonify({"error": "Invalid signature data"}), 400
        db.update_signature(receipt_id, sig)
        _regen_pdf(receipt_id)
        bust = datetime.now().strftime("%H%M%S")
        return redirect(url_for("receipt_view", receipt_id=receipt_id, v=bust))

    @app.route("/receipts/<receipt_id>/email", methods=["GET", "POST"])
    def receipt_email(receipt_id: str):
        r = db.get_receipt(receipt_id)
        if not r:
            abort(404)
        settings = db.get_settings()
        r["display_number"] = db.display_number(r)

        if request.method == "GET":
            subject = render_template_text(
                settings.get("email_subject_template", ""), r, settings,
            )
            body = render_template_text(
                settings.get("email_body_template", ""), r, settings,
            )
            return render_template(
                "email_compose.html",
                receipt=r, settings=settings,
                to=r.get("email_address") or "",
                subject=subject, body=body,
                error=None,
            )

        # POST = send
        to = request.form.get("to", "").strip()
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "")

        pdf_path = Path(r.get("pdf_path") or "")
        if not pdf_path.exists():
            pdf_path = _regen_pdf(receipt_id)

        try:
            send_via_smtp(to, subject, body, pdf_path, settings)
        except EmailError as e:
            db.update_email_status(receipt_id, "failed", to)
            return render_template(
                "email_compose.html",
                receipt=r, settings=settings,
                to=to, subject=subject, body=body,
                error=str(e),
            ), 200

        db.update_email_status(receipt_id, "sent", to)
        return redirect(url_for("receipt_view", receipt_id=receipt_id, sent="1"))

    @app.route("/api/open-pdf-folder", methods=["POST"])
    def open_pdf_folder():
        import os
        os.startfile(str(pdf_output_dir()))  # type: ignore[attr-defined]
        return ("", 204)

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
