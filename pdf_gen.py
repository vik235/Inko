import base64
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from paths import pdf_output_dir


# ---------- palette ----------
PRIMARY = HexColor("#0f766e")        # teal-700
PRIMARY_DARK = HexColor("#115e59")   # teal-800
PRIMARY_LIGHT = HexColor("#ccfbf1")  # teal-100
ACCENT = HexColor("#b45309")         # amber-700
DARK = HexColor("#0f172a")           # slate-900
TEXT = HexColor("#1e293b")           # slate-800
MUTED = HexColor("#64748b")          # slate-500
BORDER = HexColor("#e2e8f0")         # slate-200
SOFT_BG = HexColor("#f1f5f9")        # slate-100


# ---------- font registration ----------
# Built-in Helvetica lacks ₹/€/£ glyphs — register Arial from Windows so
# Indian and other currency symbols render correctly. Falls back silently.
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

_WIN_FONTS = r"C:\Windows\Fonts"
_TRIED_REGISTER = False


def _register_fonts() -> None:
    global FONT_REGULAR, FONT_BOLD, _TRIED_REGISTER
    if _TRIED_REGISTER:
        return
    _TRIED_REGISTER = True
    candidates = [
        ("Inko-Regular", "Inko-Bold", "arial.ttf", "arialbd.ttf"),
        ("Inko-Regular", "Inko-Bold", "segoeui.ttf", "segoeuib.ttf"),
    ]
    for reg_name, bold_name, reg_file, bold_file in candidates:
        reg_path = os.path.join(_WIN_FONTS, reg_file)
        bold_path = os.path.join(_WIN_FONTS, bold_file)
        if os.path.exists(reg_path) and os.path.exists(bold_path):
            try:
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                FONT_REGULAR = reg_name
                FONT_BOLD = bold_name
                return
            except Exception:
                continue


# ---------- logo ----------

class LogoFlowable(Flowable):
    """A colored rounded square with a single uppercase letter inside.

    Used as a default logo until the user uploads a real one.
    """

    def __init__(self, letter: str, size: float = 16 * mm,
                 fill: colors.Color = PRIMARY,
                 text_color: colors.Color = colors.white) -> None:
        super().__init__()
        self.letter = (letter or "I").strip()[:1].upper() or "I"
        self.size = size
        self.fill = fill
        self.text_color = text_color
        self.width = size
        self.height = size

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(self.fill)
        c.roundRect(0, 0, self.size, self.size, self.size * 0.18,
                    fill=1, stroke=0)
        c.setFillColor(self.text_color)
        font_size = self.size * 0.55
        c.setFont(FONT_BOLD, font_size)
        text_w = c.stringWidth(self.letter, FONT_BOLD, font_size)
        x = (self.size - text_w) / 2
        # Visually center the cap-height letter
        y = (self.size - font_size * 0.72) / 2
        c.drawString(x, y, self.letter)
        c.restoreState()


# ---------- page decorations ----------

BRAND_NAME = "Inko"
BRAND_SUB = "by Moviar LLC"


def _draw_brand_block(canv, x: float, y_top: float) -> None:
    """Draw the I badge + 'Inko®' + 'by Moviar LLC' block.

    `y_top` is the y-coordinate of the badge's top edge.
    """
    badge = 7 * mm
    # Q badge
    canv.setFillColor(PRIMARY)
    canv.roundRect(x, y_top - badge, badge, badge, badge * 0.22,
                   fill=1, stroke=0)
    canv.setFillColor(colors.white)
    fs = badge * 0.6
    tw = canv.stringWidth("I", FONT_BOLD, fs)
    canv.setFont(FONT_BOLD, fs)
    canv.drawString(x + (badge - tw) / 2,
                    y_top - badge + badge * 0.25, "I")

    # Brand name (top line)
    text_x = x + badge + 2.2 * mm
    name_size = 10
    canv.setFillColor(DARK)
    canv.setFont(FONT_BOLD, name_size)
    canv.drawString(text_x, y_top - 3.2 * mm, BRAND_NAME)
    name_w = canv.stringWidth(BRAND_NAME, FONT_BOLD, name_size)
    # Registered mark
    canv.setFont(FONT_REGULAR, 5.5)
    canv.setFillColor(MUTED)
    canv.drawString(text_x + name_w + 0.4 * mm,
                    y_top - 2.2 * mm, "®")

    # Sub line
    canv.setFont(FONT_REGULAR, 7)
    canv.setFillColor(MUTED)
    canv.drawString(text_x, y_top - 6.6 * mm, BRAND_SUB)


def _draw_page_chrome(canv, doc) -> None:
    width, height = A4
    canv.saveState()
    # Slim accent stripe at very top
    canv.setFillColor(PRIMARY)
    canv.rect(0, height - 3, width, 3, fill=1, stroke=0)
    # Brand block in the top margin (left)
    _draw_brand_block(canv, 20 * mm, height - 6 * mm)
    # Bottom: hairline + page number only
    canv.setStrokeColor(BORDER)
    canv.setLineWidth(0.5)
    canv.line(20 * mm, 18 * mm, width - 20 * mm, 18 * mm)
    canv.setFillColor(MUTED)
    canv.setFont(FONT_REGULAR, 8)
    canv.drawRightString(width - 20 * mm, 12 * mm,
                         f"Page {canv.getPageNumber()}")
    canv.restoreState()


# ---------- signature ----------

def _signature_image(data_url: str, max_width: float = 60 * mm,
                     max_height: float = 22 * mm) -> Image | None:
    """Decode a data: URL signature into a sized ReportLab Image, or None."""
    if not data_url or not data_url.startswith("data:image/"):
        return None
    try:
        b64 = data_url.split(",", 1)[1]
        raw = base64.b64decode(b64)
    except Exception:
        return None
    try:
        from PIL import Image as PILImage
        pil = PILImage.open(BytesIO(raw))
        w, h = pil.size
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    scale = min(max_width / w, max_height / h)
    return Image(BytesIO(raw), width=w * scale, height=h * scale)


# ---------- main ----------

def _money(amount: float, symbol: str) -> str:
    return f"{symbol}{amount:,.2f}"


def generate_receipt_pdf(receipt: dict[str, Any], settings: dict[str, str]) -> Path:
    _register_fonts()

    out_dir = pdf_output_dir()
    out_path = out_dir / f"receipt-{receipt['id']}.pdf"

    display_number = receipt.get("receipt_number") or receipt["id"]

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=28 * mm, bottomMargin=22 * mm,
        title=f"Receipt {display_number}",
        author=settings.get("business_name") or "Inko",
    )

    styles = getSampleStyleSheet()
    base = styles["Normal"]
    base.fontName = FONT_REGULAR

    heading_style = ParagraphStyle(
        "heading", parent=base, fontName=FONT_BOLD, fontSize=22, leading=26,
        textColor=DARK, spaceAfter=2,
    )
    biz_name_style = ParagraphStyle(
        "biz_name", parent=base, fontName=FONT_BOLD, fontSize=12, leading=16,
        textColor=TEXT,
    )
    biz_meta_style = ParagraphStyle(
        "biz_meta", parent=base, fontName=FONT_REGULAR, fontSize=9, leading=13,
        textColor=MUTED,
    )
    label_style = ParagraphStyle(
        "label", parent=base, fontName=FONT_BOLD, fontSize=8, leading=10,
        textColor=MUTED, spaceAfter=2,
    )
    value_style = ParagraphStyle(
        "value", parent=base, fontName=FONT_REGULAR, fontSize=11, leading=15,
        textColor=TEXT,
    )
    amount_label_style = ParagraphStyle(
        "amount_label", parent=base, fontName=FONT_BOLD, fontSize=9, leading=11,
        textColor=PRIMARY_DARK,
    )
    amount_value_style = ParagraphStyle(
        "amount_value", parent=base, fontName=FONT_BOLD, fontSize=24, leading=28,
        textColor=PRIMARY_DARK,
    )
    amount_currency_style = ParagraphStyle(
        "amount_ccy", parent=base, fontName=FONT_REGULAR, fontSize=10, leading=14,
        textColor=MUTED,
    )
    sig_style = ParagraphStyle(
        "sig", parent=base, fontName=FONT_REGULAR, fontSize=9, leading=12,
        textColor=MUTED,
    )
    footer_style = ParagraphStyle(
        "footer", parent=base, fontName=FONT_REGULAR, fontSize=10, leading=14,
        textColor=MUTED, alignment=1,
    )

    story: list = []

    # ---- header: logo + business info | receipt # / date ----
    biz_name = settings.get("business_name") or settings.get("heading") or "Inko"
    logo_letter = (
        (settings.get("business_name") or settings.get("heading") or "I")
        .strip()[:1]
        .upper()
    )
    logo = LogoFlowable(logo_letter, size=16 * mm)

    biz_lines: list[str] = []
    if settings.get("business_name"):
        biz_lines.append(f"<b><font size='12' color='#1e293b'>{settings['business_name']}</font></b>")
    if settings.get("address"):
        biz_lines.append(settings["address"].replace("\n", "<br/>"))
    contact = " · ".join(
        x for x in [settings.get("phone", ""), settings.get("email", "")] if x
    )
    if contact:
        biz_lines.append(contact)
    biz_block = Paragraph("<br/>".join(biz_lines) or biz_name, biz_meta_style)

    left_cell = Table(
        [[logo, biz_block]],
        colWidths=[18 * mm, 92 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 6),
        ]),
    )

    rid_style = ParagraphStyle(
        "rid", parent=base, fontName=FONT_BOLD,
        fontSize=14, leading=18, textColor=DARK,
    )
    right_cell = Table(
        [
            [Paragraph("RECEIPT #", label_style)],
            [Paragraph(display_number, rid_style)],
            [Spacer(1, 4)],
            [Paragraph("DATE", label_style)],
            [Paragraph(receipt["receipt_date"], value_style)],
        ],
        colWidths=[60 * mm],
        style=TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]),
    )

    header = Table(
        [[left_cell, right_cell]],
        colWidths=[110 * mm, 60 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]),
    )
    story.append(header)
    story.append(Spacer(1, 6 * mm))

    # ---- big heading band ----
    heading_text = settings.get("heading") or "Payment Receipt"
    heading_band = Table(
        [[Paragraph(heading_text, heading_style)]],
        colWidths=[170 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SOFT_BG),
            ("LINEABOVE", (0, 0), (-1, 0), 2, PRIMARY),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]),
    )
    story.append(heading_band)
    story.append(Spacer(1, 8 * mm))

    # ---- received from + date row ----
    story.append(Paragraph("RECEIVED FROM", label_style))
    story.append(Paragraph(
        f"<b><font size='14' color='#0f172a'>{receipt['payer_name']}</font></b>",
        value_style,
    ))
    story.append(Spacer(1, 8 * mm))

    # ---- amount block (highlighted) ----
    symbol = settings.get("currency_symbol") or ""
    amount_inner = Table(
        [
            [Paragraph("AMOUNT RECEIVED", amount_label_style)],
            [Paragraph(_money(float(receipt["amount"]), symbol),
                       amount_value_style)],
            [Paragraph(receipt.get("currency", ""), amount_currency_style)],
        ],
        colWidths=[170 * mm - 28],
        style=TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
            ("BOTTOMPADDING", (0, 2), (-1, 2), 0),
        ]),
    )
    amount_box = Table(
        [[amount_inner]],
        colWidths=[170 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, PRIMARY),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]),
    )
    story.append(amount_box)
    story.append(Spacer(1, 8 * mm))

    # ---- details (method, for) ----
    detail_rows = []
    if receipt.get("payment_method"):
        detail_rows.append([
            Paragraph("PAYMENT METHOD", label_style),
            Paragraph(receipt["payment_method"], value_style),
        ])
    if receipt.get("description"):
        detail_rows.append([
            Paragraph("FOR", label_style),
            Paragraph(receipt["description"], value_style),
        ])
    if detail_rows:
        details = Table(
            detail_rows,
            colWidths=[40 * mm, 130 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
            ]),
        )
        story.append(details)
        story.append(Spacer(1, 16 * mm))
    else:
        story.append(Spacer(1, 8 * mm))

    # ---- signature (per-receipt overrides default) ----
    sig_data = receipt.get("signature_png") or settings.get("signature_png", "")
    sig_img = _signature_image(sig_data)
    sig_rows = []
    if sig_img is not None:
        sig_rows.append([sig_img])
    else:
        sig_rows.append([Paragraph("_______________________________", value_style)])
    sig_rows.append([Paragraph("Authorized signature", sig_style)])
    sig_block = Table(
        sig_rows,
        colWidths=[80 * mm],
        style=TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 2),
            ("LINEBELOW", (0, 0), (0, 0), 0.4, BORDER),
        ]),
    )
    story.append(sig_block)

    # ---- footer ----
    if settings.get("footer"):
        story.append(Spacer(1, 18 * mm))
        story.append(Paragraph(settings["footer"], footer_style))

    doc.build(story, onFirstPage=_draw_page_chrome, onLaterPages=_draw_page_chrome)
    return out_path
