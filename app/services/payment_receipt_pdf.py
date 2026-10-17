"""Generate a downloadable PDF from the persisted payment receipt snapshot."""
from __future__ import annotations

from datetime import timezone
from decimal import Decimal
from unicodedata import normalize
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fpdf import FPDF


def _pdf_text(value: object) -> str:
    """Keep core-font text safe while retaining Spanish Latin-1 characters."""
    text = normalize("NFC", str(value or ""))
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _amount(value: object, currency: str) -> str:
    amount = Decimal(str(value or 0)).copy_abs().quantize(Decimal("0.01"))
    return f"{amount:.2f} {currency}"


def _rate(value: object) -> str:
    rate = Decimal(str(value)).quantize(Decimal("0.000001")).normalize()
    return format(rate, "f")


def _local_created_at(receipt: dict):
    created_at = receipt["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    try:
        hotel_tz = ZoneInfo(str(receipt.get("hotel_timezone") or "UTC"))
    except (ValueError, ZoneInfoNotFoundError):
        hotel_tz = timezone.utc
    return created_at.astimezone(hotel_tz)


def generate_payment_receipt_pdf(receipt: dict) -> bytes:
    """Render one page from ``get_payment_receipt_data`` output.

    The function accepts only the persisted receipt dictionary returned by the
    payment service; callers must perform tenant authorization first.
    """
    is_refund = str(getattr(receipt["type"], "value", receipt["type"])) == "refund"
    title = "Comprobante de devolución" if is_refund else "Comprobante de pago"
    method = getattr(receipt["method"], "value", receipt["method"])
    state = getattr(receipt["status"], "value", receipt["status"])
    currency = str(receipt["currency"])

    pdf = FPDF(format="A4")
    created_at = receipt["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    pdf.set_creation_date(created_at.astimezone(timezone.utc))
    pdf.set_title(_pdf_text(f"{title} {receipt['confirmation_code']}"))
    pdf.set_author(_pdf_text(receipt.get("hotel_name") or "Hotel"))
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_compression(False)
    pdf.add_page()

    pdf.set_font("Helvetica", style="B", size=18)
    pdf.multi_cell(0, 10, _pdf_text(receipt.get("hotel_name") or "Mi Hotel"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.multi_cell(0, 8, _pdf_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    rows = [
        ("Reserva", receipt["confirmation_code"]),
        ("Huésped", receipt.get("guest_name") or "Huésped"),
        ("Movimiento", f"#{receipt['id']}"),
        ("Fecha", _local_created_at(receipt).strftime("%Y-%m-%d %H:%M:%S %Z")),
        ("Estado", state),
        ("Medio de pago", method),
    ]
    if receipt.get("manual_reference"):
        rows.append(("Referencia manual", receipt["manual_reference"]))
    if is_refund:
        rows.append(("Importe devuelto", _amount(receipt["amount"], currency)))
        if receipt.get("refund_of_transaction_id") is not None:
            rows.append(("Movimiento original", f"#{receipt['refund_of_transaction_id']}"))
    else:
        rows.append(("Importe recibido", _amount(receipt["gross_amount"], currency)))
        fee = Decimal(str(receipt.get("fee_amount") or 0)).copy_abs().quantize(Decimal("0.01"))
        if fee > Decimal("0.00"):
            rows.append(("Cargo del medio de pago", _amount(fee, currency)))
        applied_currency = str(receipt.get("applied_currency") or currency)
        if applied_currency != currency:
            rows.append(("Importe aplicado", _amount(receipt["applied_amount"], applied_currency)))
        if receipt.get("fx_rate_snapshot") is not None:
            rows.append(
                (
                    "Cotización usada",
                    f"1 {applied_currency} = {_rate(receipt['fx_rate_snapshot'])} {currency}",
                )
            )

    pdf.set_font("Helvetica", size=11)
    for label, value in rows:
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.multi_cell(0, 7, _pdf_text(f"{label}:"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 7, _pdf_text(value), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    pdf.ln(7)
    pdf.set_font("Helvetica", size=9)
    pdf.multi_cell(
        0,
        5,
        _pdf_text("Comprobante generado con los datos registrados en el sistema del hotel."),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    output = pdf.output()
    return bytes(output)
