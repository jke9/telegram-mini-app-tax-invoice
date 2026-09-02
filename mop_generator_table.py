# -*- coding: utf-8 -*-
"""Table-first branded A4 Memorandum of Payment renderer.

This layout follows the visual grammar of traditional MOP statements: one
continuous border, ruled metadata cells, aligned calculation columns, boxed
subtotals, and a table-integrated signature area.  It reuses the premium MOP
calculation engine, including arbitrary additions and deductions.
"""

import datetime
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from mop_generator_premium import (
    BORDER,
    BRAND_BLUE,
    BRAND_BLUE_DARK,
    BRAND_NAVY,
    GREEN,
    MUTED,
    PALE_BLUE,
    PALE_GREEN,
    PALE_NAVY,
    PALE_RED,
    RED,
    TEXT,
    WHITE,
    _find_stamp,
    _wrap,
    calculate_mop,
    fmt_indian,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "jke_logo_full.png")


def draw_mop_pdf(mop_data, output_pdf):
    """Render a formal ruled-table MOP on one or more A4 pages."""
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)
    pdf = canvas.Canvas(output_pdf, pagesize=A4)
    page_w, page_h = A4
    x0, x3 = 38.0, page_w - 38.0
    x1, x2 = x0 + 328.0, x0 + 420.0
    table_w = x3 - x0
    page_bottom = 34.0
    content_bottom = 48.0
    regular, bold = "Helvetica", "Helvetica-Bold"

    contractor = str(mop_data.get("contractor_name") or "Jay Khodiyar Enterprise")
    contractor_gstin = str(mop_data.get("contractor_gstin") or "-")
    contractor_address = str(mop_data.get("contractor_address") or "")
    agency = str(mop_data.get("agency_name") or "-")
    agency_gstin = str(mop_data.get("agency_gstin") or "-")
    agency_address = str(mop_data.get("agency_address") or "")
    work_name = str(mop_data.get("work_name") or mop_data.get("project_description") or "-")
    bill_sr_no = str(mop_data.get("bill_sr_no") or "-")
    date_of_record = str(mop_data.get("date_of_record") or datetime.date.today().strftime("%d/%m/%Y"))
    ra_bill_no = str(mop_data.get("ra_bill_no") or "-")
    ra_bill_date = str(mop_data.get("ra_bill_date") or date_of_record)
    include_stamp = bool(mop_data.get("include_stamp", True))
    calculations = mop_data.get("calculations") or calculate_mop(
        mop_data.get("amount", 0),
        mop_data.get("config"),
        mop_data.get("custom_round_off"),
        mop_data.get("custom_adjustments"),
    )
    pcts = calculations["pct_config"]

    page_number = 0
    y = 0.0
    in_financial_table = False
    active_section = ""

    def stroke(color=BORDER, width=0.55):
        pdf.setStrokeColor(color)
        pdf.setLineWidth(width)

    def fill(color):
        pdf.setFillColor(color)

    def draw_logo(left, top, compact=False):
        if os.path.exists(LOGO_PATH):
            image = ImageReader(LOGO_PATH)
            image_w, image_h = image.getSize()
            max_w = 94.0 if compact else 142.0
            max_h = 29.0 if compact else 43.0
            ratio = min(max_w / image_w, max_h / image_h)
            draw_w, draw_h = image_w * ratio, image_h * ratio
            pdf.drawImage(
                image,
                left,
                top - draw_h,
                width=draw_w,
                height=draw_h,
                mask="auto",
                preserveAspectRatio=True,
            )
            return
        scale = 0.75 if compact else 1.0
        icon = 27 * scale
        fill(BRAND_BLUE)
        pdf.circle(left + 7 * scale, top - 7 * scale, 4.4 * scale, stroke=0, fill=1)
        fill(BRAND_NAVY)
        path = pdf.beginPath()
        path.moveTo(left, top - 19 * scale)
        path.curveTo(left + 8 * scale, top - 10 * scale, left + 19 * scale, top - 10 * scale, left + icon, top - 18 * scale)
        path.curveTo(left + 18 * scale, top - 21 * scale, left + 8 * scale, top - 27 * scale, left + 1 * scale, top - 31 * scale)
        path.curveTo(left - 2 * scale, top - 27 * scale, left - 2 * scale, top - 22 * scale, left, top - 19 * scale)
        pdf.drawPath(path, stroke=0, fill=1)
        tx = left + icon + 6 * scale
        pdf.setFont(bold, 12.5 * scale)
        fill(BRAND_BLUE)
        pdf.drawString(tx, top - 10 * scale, "JAY")
        pdf.setFont(bold, 10.8 * scale)
        fill(BRAND_NAVY)
        pdf.drawString(tx, top - 23 * scale, "KHODIYAR")
        pdf.setFont(bold, 4.7 * scale)
        pdf.drawString(tx, top - 31 * scale, "E N T E R P R I S E")

    def footer():
        pdf.setFont(regular, 6.4)
        fill(MUTED)
        pdf.drawString(x0 + 4, page_bottom + 5, "Computer-generated Memorandum of Payment")
        pdf.drawRightString(x3 - 4, page_bottom + 5, f"Page {page_number}")

    def start_page(continuation=False):
        nonlocal page_number, y, in_financial_table
        page_number += 1
        fill(WHITE)
        pdf.rect(0, 0, page_w, page_h, stroke=0, fill=1)
        stroke(BRAND_NAVY, 1.0)
        pdf.rect(x0, page_bottom, table_w, page_h - page_bottom - 28, stroke=1, fill=0)
        fill(BRAND_BLUE)
        pdf.rect(x0, page_h - 31, table_w, 3, stroke=0, fill=1)

        if continuation:
            top = page_h - 42
            draw_logo(x0 + 10, top, compact=True)
            pdf.setFont(bold, 9.0)
            fill(BRAND_NAVY)
            pdf.drawRightString(x3 - 10, top - 11, "MEMORANDUM OF PAYMENT - CONTINUED")
            pdf.setFont(regular, 6.8)
            fill(MUTED)
            pdf.drawRightString(x3 - 10, top - 23, f"{ra_bill_no} | {ra_bill_date}")
            y = page_h - 83
        else:
            top = page_h - 41
            draw_logo(x0 + 12, top)
            pdf.setFont(bold, 15)
            fill(BRAND_NAVY)
            pdf.drawRightString(x3 - 12, top - 10, "MEMORANDUM OF PAYMENT")
            pdf.setFont(bold, 7.5)
            fill(MUTED)
            pdf.drawRightString(x3 - 12, top - 25, f"DATE: {record_date}  |  GSTIN: {contractor_gstin}")
            y = page_h - 89
        in_financial_table = False

    def finish_page():
        footer()
        pdf.showPage()

    def next_page(section_title=None):
        nonlocal active_section
        finish_page()
        start_page(True)
        if section_title:
            active_section = section_title
            draw_financial_header()
            draw_section(section_title + " (CONTINUED)")

    def ensure(height, section_title=None):
        if y - height < content_bottom:
            next_page(section_title or active_section or "PAYMENT DETAILS")

    def draw_cell(left, right, top, height, label, value, fill_color=WHITE, font_size=7.5, value_bold=False):
        fill(fill_color)
        stroke(BORDER, 0.45)
        pdf.rect(left, top - height, right - left, height, stroke=1, fill=1)
        pdf.setFont(bold, 6.2)
        fill(MUTED)
        pdf.drawString(left + 7, top - 10, label.upper())
        lines = _wrap(value, bold if value_bold else regular, font_size, right - left - 14)[:3]
        pdf.setFont(bold if value_bold else regular, font_size)
        fill(TEXT)
        text_y = top - 21
        for line in lines:
            pdf.drawString(left + 7, text_y, line)
            text_y -= 8.5

    def metadata_block():
        nonlocal y
        mid = x0 + table_w / 2
        row_h = 31
        draw_cell(x0, mid, y, row_h, "Name of Agency", agency, value_bold=True)
        draw_cell(mid, x3, y, row_h, "Agency GSTIN", agency_gstin)
        y -= row_h

        if agency_address:
            address_lines = _wrap(agency_address, regular, 7.2, table_w - 14)
            address_h = max(24, 15 + 8.5 * len(address_lines))
            draw_cell(x0, x3, y, address_h, "Agency Address", agency_address, font_size=7.2)
            y -= address_h

        work_lines = _wrap(work_name, regular, 7.5, table_w - 14)
        work_h = max(34, 18 + 8.5 * len(work_lines))
        draw_cell(x0, x3, y, work_h, "Name of Work / Project", work_name, fill_color=PALE_BLUE, font_size=7.5)
        y -= work_h

        one_half = table_w / 2
        draw_cell(x0, x0 + one_half, y, row_h, "RA Bill No.", ra_bill_no, value_bold=True)
        draw_cell(x0 + one_half, x3, y, row_h, "RA Bill Date", ra_bill_date, value_bold=True)
        y -= row_h

        fill(BRAND_NAVY)
        pdf.rect(x0, y - 23, table_w, 23, stroke=0, fill=1)
        pdf.setFont(bold, 10.5)
        fill(WHITE)
        pdf.drawCentredString((x0 + x3) / 2, y - 15.5, "MEMORANDUM OF PAYMENT")
        y -= 23

    def draw_financial_header():
        nonlocal y, in_financial_table
        fill(PALE_BLUE)
        stroke(BRAND_NAVY, 0.65)
        pdf.rect(x0, y - 18, table_w, 18, stroke=1, fill=1)
        pdf.line(x1, y, x1, y - 18)
        pdf.line(x2, y, x2, y - 18)
        pdf.setFont(bold, 6.8)
        fill(BRAND_NAVY)
        pdf.drawString(x0 + 7, y - 12, "PARTICULARS")
        pdf.drawCentredString((x1 + x2) / 2, y - 12, "BASIS / RATE")
        pdf.drawCentredString((x2 + x3) / 2, y - 12, "AMOUNT (INR)")
        y -= 18
        in_financial_table = True

    def draw_section(title):
        nonlocal y, active_section
        ensure(18, title)
        active_section = title.replace(" (CONTINUED)", "")
        fill(colors.HexColor("#DCECF7"))
        stroke(BRAND_NAVY, 0.65)
        pdf.rect(x0, y - 17, table_w, 17, stroke=1, fill=1)
        pdf.setFont(bold, 7.6)
        fill(BRAND_NAVY)
        pdf.drawString(x0 + 7, y - 11.5, title)
        y -= 17

    def table_row(label, amount, basis="", style="normal", detail=""):
        nonlocal y
        label_lines = _wrap(label, bold if style in {"subtotal", "grand"} else regular, 7.35, x1 - x0 - 14)
        if detail:
            detail_lines = _wrap(detail, regular, 6.2, x1 - x0 - 14)
        else:
            detail_lines = []
        height = max(16, 8 + 8 * len(label_lines) + (7 * len(detail_lines) if detail_lines else 0))
        ensure(height, active_section)
        if style == "grand":
            background, label_color, amount_color = BRAND_BLUE, WHITE, WHITE
        elif style == "subtotal":
            background, label_color, amount_color = PALE_BLUE, BRAND_NAVY, BRAND_BLUE_DARK
        elif style == "deduct":
            background, label_color, amount_color = colors.HexColor("#FFF9F8"), TEXT, RED
        elif style == "add":
            background, label_color, amount_color = colors.HexColor("#F7FCFA"), TEXT, GREEN
        else:
            background, label_color, amount_color = WHITE, TEXT, TEXT
        fill(background)
        stroke(BORDER, 0.4)
        pdf.rect(x0, y - height, table_w, height, stroke=1, fill=1)
        pdf.line(x1, y, x1, y - height)
        pdf.line(x2, y, x2, y - height)
        font = bold if style in {"subtotal", "grand"} else regular
        pdf.setFont(font, 7.35 if style != "grand" else 8.2)
        fill(label_color)
        text_y = y - 11
        for line in label_lines:
            pdf.drawString(x0 + 7, text_y, line)
            text_y -= 8
        if detail_lines:
            pdf.setFont(regular, 6.2)
            fill(WHITE if style == "grand" else MUTED)
            for line in detail_lines:
                pdf.drawString(x0 + 12, text_y, line)
                text_y -= 7
        pdf.setFont(regular if style not in {"subtotal", "grand"} else bold, 7.0)
        fill(WHITE if style == "grand" else MUTED)
        for index, line in enumerate(_wrap(basis, regular, 6.6, x2 - x1 - 10)[:2]):
            pdf.drawCentredString((x1 + x2) / 2, y - 11 - index * 7, line)
        pdf.setFont(bold if style in {"subtotal", "grand"} else regular, 7.5 if style != "grand" else 8.4)
        fill(amount_color)
        pdf.drawRightString(x3 - 7, y - (height / 2) - 2.5, fmt_indian(amount))
        y -= height

    def amount_words_and_signature():
        nonlocal y
        word_lines = _wrap(calculations["amount_in_words"], bold, 7.2, table_w - 16)
        words_h = max(30, 18 + 8 * len(word_lines))
        signature_h = 72
        ensure(words_h + signature_h + 2, "PAYMENT SUMMARY")

        fill(PALE_BLUE)
        stroke(BRAND_NAVY, 0.65)
        pdf.rect(x0, y - words_h, table_w, words_h, stroke=1, fill=1)
        pdf.setFont(bold, 6.2)
        fill(BRAND_BLUE_DARK)
        pdf.drawString(x0 + 7, y - 10, "AMOUNT IN WORDS")
        pdf.setFont(bold, 7.2)
        fill(BRAND_NAVY)
        line_y = y - 21
        for line in word_lines:
            pdf.drawCentredString((x0 + x3) / 2, line_y, line)
            line_y -= 8
        y -= words_h

        mid = x0 + table_w * 0.62
        fill(WHITE)
        stroke(BRAND_NAVY, 0.65)
        pdf.rect(x0, y - signature_h, table_w, signature_h, stroke=1, fill=1)
        pdf.line(mid, y, mid, y - signature_h)
        pdf.setFont(bold, 7.0)
        fill(TEXT)
        pdf.drawString(x0 + 7, y - 14, "Subject to Ahmedabad Jurisdiction")
        pdf.setFont(regular, 6.8)
        fill(MUTED)
        pdf.drawString(x0 + 7, y - 29, "E. & O. E.")
        pdf.drawString(x0 + 7, y - 42, "This is a computer-generated document.")
        if contractor_address:
            pdf.drawString(x0 + 7, y - 56, _wrap(contractor_address, regular, 6.3, mid - x0 - 14)[0])

        pdf.setFont(bold, 7.2)
        fill(BRAND_NAVY)
        pdf.drawString(mid + 7, y - 14, f"For {contractor}")
        stamp = _find_stamp(contractor) if include_stamp else None
        if stamp:
            try:
                pdf.drawImage(stamp, x3 - 104, y - 57, width=76, height=37, mask="auto", preserveAspectRatio=True)
            except Exception:
                pass
        pdf.setFont(bold, 7.0)
        fill(TEXT)
        pdf.drawRightString(x3 - 7, y - 59, "Authorised Signatory")
        pdf.setFont(regular, 6.4)
        fill(MUTED)
        pdf.drawRightString(x3 - 7, y - 68, "Contractor")
        y -= signature_h

    start_page(False)
    metadata_block()
    draw_financial_header()

    draw_section("A. WORK VALUE")
    table_row("Basic work value", calculations["basic_work"], "Gross / 1.18")
    table_row("GST component", calculations["gross_amount"] - calculations["basic_work"], "18%")
    table_row("Total work done amount as per RA Bill", calculations["gross_amount"], style="subtotal")

    draw_section("B. DEDUCTIONS FROM GOVERNMENT / AGENCY")
    table_row("Income Tax / TDS", calculations["agency_tds"], f"{pcts['agency_tds_pct']:.2f}%", style="deduct")
    table_row("SGST TDS", calculations["agency_sgst"], f"{pcts['agency_sgst_tds_pct']:.2f}%", style="deduct")
    table_row("CGST TDS", calculations["agency_cgst"], f"{pcts['agency_cgst_tds_pct']:.2f}%", style="deduct")
    table_row("Total agency deductions", calculations["agency_deductions_total"], style="subtotal")
    table_row("Net work done (A - B)", calculations["net_work_done"], style="subtotal")
    table_row("Administrative and head expense", calculations["admin_expense"], f"{pcts['admin_expense_pct']:.2f}%", style="deduct")

    draw_section("C. OUR BILL AMOUNT")
    table_row("Basic amount", calculations["our_basic"])
    table_row("SGST", calculations["our_sgst"], "9.00%")
    table_row("CGST", calculations["our_cgst"], "9.00%")
    table_row("Gross bill amount", calculations["our_bill_gross"], style="subtotal")

    custom_rows = calculations.get("custom_adjustments", [])
    estimated_d_height = 17 + (6 + len(custom_rows)) * 18 + 105
    if y - estimated_d_height < content_bottom:
        next_page("D. FINAL DEDUCTIONS / ADJUSTMENTS")
    else:
        draw_section("D. FINAL DEDUCTIONS / ADJUSTMENTS")

    table_row("Income Tax / TDS", calculations["it_tds"], f"{pcts['it_tds_pct']:.2f}%", style="deduct")
    table_row("Retention money", calculations["retention"], f"{pcts['retention_pct']:.2f}%", style="deduct")
    table_row("Labour cess", calculations["labour_cess"], f"{pcts['labour_cess_pct']:.2f}%", style="deduct")
    table_row("Testing fee", calculations["testing_fee"], f"{pcts['testing_fee_pct']:.2f}%", style="deduct")
    for row in custom_rows:
        if row["calculation"] == "percent":
            basis = f"{row['value']:.2f}%"
            detail = "Base: " + row["base"].replace("_", " ").title()
        else:
            basis = "Fixed"
            detail = ""
        table_row(
            row["label"],
            row["amount"],
            basis,
            style="add" if row["operation"] == "add" else "deduct",
            detail=detail,
        )
    table_row("Round off", calculations["round_off"], "Manual" if mop_data.get("custom_round_off") is not None else "Auto")
    table_row("TOTAL PAYABLE AMOUNT", calculations["net_payable"], "FINAL", style="grand")
    amount_words_and_signature()

    finish_page()
    pdf.save()
    return output_pdf


if __name__ == "__main__":
    result = calculate_mop(15_312_151)
    output = os.path.join(BASE_DIR, "output", "pdf", "table_mop_sample.pdf")
    draw_mop_pdf({
        "contractor_name": "Jay Khodiyar Enterprise",
        "contractor_gstin": "24BJHPP5061K1ZZ",
        "agency_name": "YOGI CONSTRUCTION CO.",
        "agency_gstin": "24AAAFY3044N1Z1",
        "work_name": "Laying of Water Distribution Network and Sewerage Network in Central Zone of AMC area.",
        "bill_sr_no": "19/26-27",
        "date_of_record": "24/08/2026",
        "ra_bill_no": "RA BILL NO. 07 (Vatva)",
        "ra_bill_date": "24/08/2026",
        "calculations": result,
        "include_stamp": True,
    }, output)
    print(output)
