"""Minimal text PDF builder for B2B draft / order proforma (no extra deps)."""

from __future__ import annotations

from decimal import Decimal


_TR = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "Ç": "C",
        "Ğ": "G",
        "İ": "I",
        "Ö": "O",
        "Ş": "S",
        "Ü": "U",
    }
)


def _ascii(text: str) -> str:
    return (text or "").translate(_TR)


def _pdf_escape(text: str) -> str:
    return _ascii(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _money(value: Decimal | float | int | str, digits: int = 2) -> str:
    try:
        q = Decimal(str(value)).quantize(Decimal(10) ** -digits)
    except Exception:
        return str(value)
    return f"{q:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_text_pdf(lines: list[str], *, title: str = "Proforma") -> bytes:
    """Build a single-page Helvetica PDF from plain text lines."""
    content: list[str] = ["BT", "/F1 11 Tf", "50 800 Td", f"({_pdf_escape(title)}) Tj", "0 -18 Td", "/F1 9 Tf"]
    for i, line in enumerate(lines):
        if i > 0:
            content.append("0 -12 Td")
        content.append(f"({_pdf_escape(line[:110])}) Tj")
        if i > 58:
            content.append("0 -12 Td")
            content.append("(… devamı siparis fisinde) Tj")
            break
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(out)


def draft_proforma_lines(*, org_name: str, org_code: str, lines, gold_rate: str = "") -> list[str]:
    rows = [
        f"Bayi: {org_name} ({org_code})",
        f"Kalem: {len(lines)}",
        "-" * 72,
    ]
    total_try = Decimal("0")
    total_usd = Decimal("0")
    for i, line in enumerate(lines, start=1):
        try_amt = Decimal(str(line.unit_wholesale_try)) * line.qty
        usd_amt = Decimal(str(line.unit_wholesale_usd)) * line.qty
        total_try += try_amt
        total_usd += usd_amt
        supply = "Stoktan" if line.supply_type == "STOCK" else "Atolye"
        rows.append(
            f"{i}. {line.sku} | {line.title} | {line.qty} adet | {supply} | "
            f"${_money(usd_amt)} / {_money(try_amt)} TL"
        )
    rows.append("-" * 72)
    rows.append(f"Toplam: ${_money(total_usd)} / {_money(total_try)} TL")
    if gold_rate:
        rows.append(f"Has referans: {gold_rate} TL/gr")
    rows.append("Not: Stok ayirma proforma onayinda yapilir. ±%5 terazi farki teslimatta kesinlesir.")
    return rows


def order_proforma_lines(order) -> list[str]:
    rows = [
        f"Fis No: {order.order_no}",
        f"Bayi: {order.organization.name} ({order.organization.code})",
        f"Durum: {order.status}",
        "-" * 72,
    ]
    for i, line in enumerate(order.lines.all(), start=1):
        supply = "Stoktan" if line.supply_type == "STOCK" else "Atolye"
        rows.append(
            f"{i}. {line.sku} | {line.title} | {line.qty} adet | {supply} | "
            f"${_money(line.unit_wholesale_usd * line.qty)} / "
            f"{_money(line.unit_wholesale_try * line.qty)} TL"
        )
    rows.append("-" * 72)
    rows.append(
        f"Toplam: {order.total_pieces} adet · ${_money(order.total_wholesale_usd)} / "
        f"{_money(order.total_wholesale_try)} TL"
    )
    rows.append("Not: El isciligi ve dokum kaynakli ±%5 terazi farki teslimatta kesinlesir.")
    return rows
