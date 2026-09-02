# -*- coding: utf-8 -*-
"""Premium Annexure-I PDF generator.

Replicates the PIPLAJ B2B FORMAT.xlsx Annexure-I table structure:
  Section 1 (A–H): Contractor Bill Reconciliation
  Section 2 (I–N): Sub-Contractor Payment cum Invoice Summary
  Right Panel:      Sarthi Charges / B2B compact summary

Uses the Jay Khodiyar Enterprise brand palette and reuses utilities from
mop_generator_premium.py.
"""

import math
import os
from typing import Any, Dict, Optional

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
    fmt_indian,
    num_to_words_indian,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "jke_logo_full.png")

# Additional palette for the annexure
SECTION_FILL = colors.HexColor("#1A3A5C")       # Dark navy for section headers
SECTION_TEXT = colors.white
HEADER_FILL = colors.HexColor("#E8F0FA")         # Light blue for table headers
SUBTOTAL_FILL = colors.HexColor("#E2EDF8")        # Soft blue for subtotals
GRAND_FILL = BRAND_BLUE                           # Brand blue for grand totals
GRAND_TEXT = colors.white
DEDUCT_FILL = colors.HexColor("#FFF7F6")          # Very pale red for deductions
DEDUCT_TEXT = colors.HexColor("#B84B43")
ADD_FILL = colors.HexColor("#F4FBF8")             # Very pale green for additions
ADD_TEXT = colors.HexColor("#167D61")
ZEBRA_EVEN = colors.white
ZEBRA_ODD = colors.HexColor("#F8FAFC")
GRID_COLOR = colors.HexColor("#C8D6E5")
GRID_DARK = colors.HexColor("#8FA7BE")
RIGHT_PANEL_HEADER = colors.HexColor("#2C5F8A")
RIGHT_PANEL_BG = colors.HexColor("#F0F6FC")
RIGHT_PANEL_TOTAL_BG = colors.HexColor("#D6E8F7")


def _num(value, default=0.0):
    """Safe float conversion."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def calculate_annexure(
    sub_contract_value: float,
    sgst_rate: float = 9.0,
    cgst_rate: float = 9.0,
    round_off_gst: float = -0.67,
    sgst_tds_rate: float = 1.0,
    cgst_tds_rate: float = 1.0,
    tds_rate: float = 1.0,
    cess_wf_rate: float = 1.0,
    retention_rate: float = 2.0,
    testing_rate: float = 0.5,
    office_expense_rate: float = 2.0,
    sublet_bill_value: Optional[float] = None,
    sublet_round_off: float = 0.46,
    sublet_tds_rate: float = 1.0,
    sublet_tds_round_off: float = -0.47,
    sublet_on_hold_retention: Optional[float] = None,
    sublet_on_hold_testing: Optional[float] = None,
    sarthi_charges_rate: float = 2.0,
) -> Dict[str, Any]:
    """Calculate all Annexure-I values from the sub-contract base value.

    Returns a dict with all line items for both sections and the right panel.
    """
    base = _num(sub_contract_value)

    # --- Section A-H: Contractor Bill Reconciliation ---
    sgst = base * sgst_rate / 100.0
    cgst = base * cgst_rate / 100.0
    total_gst = sgst + cgst + round_off_gst
    total_after_gst = base + total_gst  # C

    sgst_tds = base * sgst_tds_rate / 100.0
    cgst_tds = base * cgst_tds_rate / 100.0
    tds = math.ceil(base * tds_rate / 100.0)
    cess_wf = math.ceil(base * cess_wf_rate / 100.0)
    total_deductions = sgst_tds + cgst_tds + tds + cess_wf  # D

    retention = round(total_after_gst * retention_rate / 100.0)
    testing = round(total_after_gst * testing_rate / 100.0)
    total_on_hold = retention + testing  # E

    net_amount = total_after_gst - total_deductions - total_on_hold  # F

    office_expense = round(base * office_expense_rate / 100.0)
    total_charges = office_expense  # G

    net_sublet_bill = total_after_gst - total_deductions - total_charges  # H

    # --- Section I-N: Sub-Contractor Payment Summary ---
    if sublet_bill_value is None:
        sublet_bill_value = base - office_expense  # approximate

    sub_sgst = sublet_bill_value * sgst_rate / 100.0
    sub_cgst = sublet_bill_value * cgst_rate / 100.0
    sub_total_gst = sub_sgst + sub_cgst + sublet_round_off
    sub_total_after_gst = sublet_bill_value + sub_total_gst  # K

    sub_retention = retention if sublet_on_hold_retention is None else sublet_on_hold_retention
    sub_testing = testing if sublet_on_hold_testing is None else sublet_on_hold_testing
    sub_on_hold = sub_retention + sub_testing  # L

    sub_tds_raw = sublet_bill_value * sublet_tds_rate / 100.0
    sub_tds = sub_tds_raw  # M (raw, before round-off applied at net level)

    sub_net_payable = sub_total_after_gst - sub_on_hold - sub_tds + sublet_tds_round_off  # N

    # --- Right Panel: Sarthi Charges / B2B ---
    gst_18 = base * 18.0 / 100.0
    total_with_gst_right = base + gst_18
    right_sgst = base * 1.0 / 100.0  # 1% for right panel display
    right_cgst = base * 1.0 / 100.0
    right_it = tds
    right_cess = cess_wf
    total_with_deduction = total_with_gst_right - (right_sgst + right_cgst + right_it + right_cess)
    right_retention = retention
    right_testing = testing
    net_bill = total_with_deduction - right_retention - right_testing
    amount_to_sarthi = round(net_bill)
    b2b_bill = amount_to_sarthi - office_expense

    return {
        # Section A
        "sub_contract_value": base,
        # Section B
        "sgst": sgst,
        "cgst": cgst,
        "round_off_gst": round_off_gst,
        "total_gst": total_gst,
        # Section C
        "total_after_gst": total_after_gst,
        # Section D
        "sgst_tds": sgst_tds,
        "cgst_tds": cgst_tds,
        "tds": tds,
        "cess_wf": cess_wf,
        "total_deductions": total_deductions,
        # Section E
        "retention": retention,
        "testing": testing,
        "total_on_hold": total_on_hold,
        # Section F
        "net_amount": net_amount,
        # Section G
        "office_expense": office_expense,
        "total_charges": total_charges,
        # Section H
        "net_sublet_bill": net_sublet_bill,
        # Section I
        "sublet_bill_value": sublet_bill_value,
        # Section J
        "sub_sgst": sub_sgst,
        "sub_cgst": sub_cgst,
        "sublet_round_off": sublet_round_off,
        # Section K
        "sub_total_after_gst": sub_total_after_gst,
        # Section L
        "sub_retention": sub_retention,
        "sub_testing": sub_testing,
        "sub_on_hold": sub_on_hold,
        # Section M
        "sub_tds": sub_tds,
        "sublet_tds_round_off": sublet_tds_round_off,
        # Section N
        "sub_net_payable": sub_net_payable,
        # Right Panel
        "right_base": base,
        "right_gst_18": gst_18,
        "right_total_with_gst": total_with_gst_right,
        "right_sgst": right_sgst,
        "right_cgst": right_cgst,
        "right_it": right_it,
        "right_cess": right_cess,
        "right_total_with_deduction": total_with_deduction,
        "right_retention": right_retention,
        "right_testing": right_testing,
        "right_net_bill": net_bill,
        "right_amount_to_sarthi": amount_to_sarthi,
        "right_sarthi_charges": office_expense,
        "right_b2b_bill": b2b_bill,
        # Rates (for display)
        "sgst_rate": sgst_rate,
        "cgst_rate": cgst_rate,
        "sgst_tds_rate": sgst_tds_rate,
        "cgst_tds_rate": cgst_tds_rate,
        "tds_rate": tds_rate,
        "cess_wf_rate": cess_wf_rate,
        "retention_rate": retention_rate,
        "testing_rate": testing_rate,
        "office_expense_rate": office_expense_rate,
        "sarthi_charges_rate": sarthi_charges_rate,
    }


def draw_annexure_pdf(data: Dict[str, Any], output_pdf: str) -> str:
    """Render a premium Annexure-I PDF matching the PIPLAJ B2B FORMAT structure.

    Parameters
    ----------
    data : dict
        Keys:
            contractor_name, contractor_gstin, buyer_name, buyer_gstin,
            buyer_address, buyer_contact_person, buyer_mobile,
            work_name, invoice_no, ref_inv_no, invoice_date, ref_no,
            ra_bill_label (e.g. "RA 01"),
            calculations (output of calculate_annexure),
            include_stamp (bool)
    output_pdf : str
        Output file path.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)
    pdf = canvas.Canvas(output_pdf, pagesize=A4)
    page_w, page_h = A4
    regular, bold = "Helvetica", "Helvetica-Bold"

    # Margins
    margin_left = 32.0
    margin_right = 32.0
    margin_top = 28.0
    margin_bottom = 34.0
    content_w = page_w - margin_left - margin_right
    x0 = margin_left
    x_end = page_w - margin_right

    contractor = str(data.get("contractor_name") or "Jay Khodiyar Enterprise")
    contractor_gstin = str(data.get("contractor_gstin") or "-")
    buyer = str(data.get("buyer_name") or "Sarthi Construction")
    buyer_gstin = str(data.get("buyer_gstin") or "-")
    work_name = str(data.get("work_name") or "-")
    ra_label = str(data.get("ra_bill_label") or "RA 01")
    include_stamp = bool(data.get("include_stamp", True))
    calc = data.get("calculations") or {}

    # Column boundaries for 5-column table
    c1 = x0 + 36            # end of Sr no.
    c2 = c1 + 168           # end of Particulars
    c3 = c2 + 80            # end of Details
    c4 = c3 + 68            # end of Amount (sub)
    c5 = x_end              # end of Amount (total)
    th_h = 16               # table header height

    page_number = 0
    y = page_h - margin_top
    row_counter = [0]

    def fill(color):
        pdf.setFillColor(color)

    def stroke(color=GRID_COLOR, width=0.4):
        pdf.setStrokeColor(color)
        pdf.setLineWidth(width)

    def hline(x1_pos, x2_pos, yy, color=GRID_COLOR, width=0.4):
        stroke(color, width)
        pdf.line(x1_pos, yy, x2_pos, yy)

    def vline(xx, y1, y2, color=GRID_COLOR, width=0.4):
        stroke(color, width)
        pdf.line(xx, y1, xx, y2)

    def draw_logo(lx, ly, compact=False):
        if os.path.exists(LOGO_PATH):
            img = ImageReader(LOGO_PATH)
            iw, ih = img.getSize()
            max_w = 90.0 if compact else 135.0
            max_h = 28.0 if compact else 40.0
            ratio = min(max_w / iw, max_h / ih)
            dw, dh = iw * ratio, ih * ratio
            pdf.drawImage(img, lx, ly - dh, width=dw, height=dh,
                          mask="auto", preserveAspectRatio=True)
            return
        # Fallback vector mark
        scale = 0.7 if compact else 1.0
        icon = 27 * scale
        fill(BRAND_BLUE)
        pdf.circle(lx + 7 * scale, ly - 7 * scale, 4.4 * scale, stroke=0, fill=1)
        fill(BRAND_NAVY)
        p = pdf.beginPath()
        p.moveTo(lx, ly - 19 * scale)
        p.curveTo(lx + 8 * scale, ly - 10 * scale,
                  lx + 19 * scale, ly - 10 * scale,
                  lx + icon, ly - 18 * scale)
        p.curveTo(lx + 18 * scale, ly - 21 * scale,
                  lx + 8 * scale, ly - 27 * scale,
                  lx + 1 * scale, ly - 31 * scale)
        p.curveTo(lx - 2 * scale, ly - 27 * scale,
                  lx - 2 * scale, ly - 22 * scale,
                  lx, ly - 19 * scale)
        pdf.drawPath(p, stroke=0, fill=1)
        tx = lx + icon + 6 * scale
        pdf.setFont(bold, 12.5 * scale)
        fill(BRAND_BLUE)
        pdf.drawString(tx, ly - 10 * scale, "JAY")
        pdf.setFont(bold, 10.8 * scale)
        fill(BRAND_NAVY)
        pdf.drawString(tx, ly - 23 * scale, "KHODIYAR")
        pdf.setFont(bold, 4.7 * scale)
        pdf.drawString(tx, ly - 31 * scale, "E N T E R P R I S E")

    def page_footer():
        pdf.setFont(regular, 6.2)
        fill(MUTED)
        pdf.drawString(x0 + 2, margin_bottom - 8, "Computer-generated Annexure Statement")
        pdf.drawRightString(x_end - 2, margin_bottom - 8, f"Page {page_number}")

    def start_page(continuation=False):
        nonlocal page_number, y
        page_number += 1
        fill(colors.white)
        pdf.rect(0, 0, page_w, page_h, stroke=0, fill=1)

        # Top accent bar
        fill(BRAND_BLUE)
        pdf.rect(0, page_h - 6, page_w, 6, stroke=0, fill=1)

        # Outer border
        stroke(BRAND_NAVY, 1.0)
        pdf.rect(x0 - 2, margin_bottom - 2, content_w + 4,
                 page_h - margin_top - margin_bottom + 4, stroke=1, fill=0)

        y = page_h - margin_top - 4

        if continuation:
            draw_logo(x0 + 4, y, compact=True)
            pdf.setFont(bold, 9.5)
            fill(BRAND_NAVY)
            pdf.drawRightString(x_end - 6, y - 12, "ANNEXURE - I (CONTINUED)")
            pdf.setFont(regular, 6.8)
            fill(MUTED)
            pdf.drawRightString(x_end - 6, y - 23, f"{ra_label} | {contractor}")
            hline(x0, x_end, y - 32, GRID_DARK, 0.6)
            y -= 40
        else:
            y -= 2

    def ensure(height):
        nonlocal y
        if y - height < margin_bottom + 14:
            page_footer()
            pdf.showPage()
            start_page(continuation=True)

    def draw_table_header():
        """Draw the 5-column table header row."""
        nonlocal y
        fill(HEADER_FILL)
        stroke(GRID_DARK, 0.5)
        pdf.rect(x0, y - th_h, c5 - x0, th_h, stroke=1, fill=1)
        for cx in [c1, c2, c3, c4]:
            vline(cx, y, y - th_h, GRID_DARK, 0.5)
        pdf.setFont(bold, 7.0)
        fill(BRAND_NAVY)
        pdf.drawCentredString((x0 + c1) / 2, y - 11, "Sr no.")
        pdf.drawCentredString((c1 + c2) / 2, y - 11, "Particulars")
        pdf.drawCentredString((c2 + c3) / 2, y - 11, "Details")
        pdf.drawCentredString((c3 + c4) / 2, y - 11, "Amount")
        pdf.drawCentredString((c4 + c5) / 2, y - 11, "Amount")
        y -= th_h

    def table_row(sr, label, detail="", amt_sub=None, amt_total=None,
                  style="normal", is_bold_label=False, indent=0):
        """Draw a single annexure table row.

        style: 'normal', 'subtotal', 'grand', 'deduct', 'add', 'section_total'
        """
        nonlocal y
        font_label = bold if (is_bold_label or style in (
            "subtotal", "grand", "section_total")) else regular
        max_label_w = c2 - c1 - 14 - indent
        label_lines = _wrap(label, font_label, 7.2, max_label_w)
        row_h = max(16, 7 + 8.5 * len(label_lines))

        ensure(row_h)

        # Background
        if style == "grand":
            bg, lbl_c, amt_c = GRAND_FILL, GRAND_TEXT, GRAND_TEXT
        elif style in ("subtotal", "section_total"):
            bg, lbl_c, amt_c = SUBTOTAL_FILL, BRAND_NAVY, BRAND_BLUE_DARK
        elif style == "deduct":
            bg, lbl_c, amt_c = DEDUCT_FILL, TEXT, DEDUCT_TEXT
        elif style == "add":
            bg, lbl_c, amt_c = ADD_FILL, TEXT, ADD_TEXT
        else:
            bg = ZEBRA_EVEN if row_counter[0] % 2 == 0 else ZEBRA_ODD
            lbl_c, amt_c = TEXT, TEXT

        fill(bg)
        stroke(GRID_COLOR, 0.35)
        pdf.rect(x0, y - row_h, c5 - x0, row_h, stroke=1, fill=1)

        # Column separators
        for cx in [c1, c2, c3, c4]:
            vline(cx, y, y - row_h, GRID_COLOR, 0.35)

        # Sr no.
        if sr:
            pdf.setFont(
                bold if style in ("subtotal", "grand", "section_total")
                else regular, 7.0)
            fill(lbl_c)
            pdf.drawCentredString((x0 + c1) / 2, y - row_h / 2 - 2, str(sr))

        # Label (Particulars)
        pdf.setFont(font_label, 7.2)
        fill(lbl_c)
        text_y = y - 11
        for line in label_lines:
            pdf.drawString(c1 + 6 + indent, text_y, line)
            text_y -= 8.5

        # Detail
        if detail:
            pdf.setFont(regular, 6.8)
            fill(MUTED if style != "grand" else GRAND_TEXT)
            detail_lines = _wrap(str(detail), regular, 6.8, c3 - c2 - 10)
            dt_y = y - 11
            for dl in detail_lines[:2]:
                pdf.drawString(c2 + 5, dt_y, dl)
                dt_y -= 7.5

        # Amount (sub-column)
        if amt_sub is not None:
            pdf.setFont(regular, 7.0)
            fill(amt_c)
            pdf.drawRightString(c4 - 5, y - row_h / 2 - 2, fmt_indian(amt_sub))

        # Amount (total column)
        if amt_total is not None:
            fnt = bold if style in ("subtotal", "grand", "section_total") else regular
            fsz = 7.8 if style == "grand" else 7.2
            pdf.setFont(fnt, fsz)
            fill(amt_c)
            pdf.drawRightString(c5 - 5, y - row_h / 2 - 2, fmt_indian(amt_total))

        y -= row_h
        row_counter[0] += 1

    # ═══════════════════════════════════════════════════════════════════
    # PAGE 1 — HEADER
    # ═══════════════════════════════════════════════════════════════════
    start_page(False)

    # Logo
    draw_logo(x0 + 6, y)
    y -= 46

    # Title bar
    title_h = 26
    fill(SECTION_FILL)
    pdf.rect(x0, y - title_h, content_w, title_h, stroke=0, fill=1)
    pdf.setFont(bold, 14)
    fill(SECTION_TEXT)
    pdf.drawCentredString(x0 + content_w / 2, y - 18, "Annexure - I")
    y -= title_h + 4

    # Sub-heading: contractor / buyer
    info_h = 14
    fill(HEADER_FILL)
    pdf.rect(x0, y - info_h, content_w, info_h, stroke=0, fill=1)
    pdf.setFont(bold, 7.0)
    fill(BRAND_NAVY)
    pdf.drawString(x0 + 6, y - 10, f"For: {contractor}")
    pdf.drawRightString(x_end - 6, y - 10, f"To: {buyer}")
    y -= info_h + 6

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1: CONTRACTOR BILL RECONCILIATION (A–H)
    # ═══════════════════════════════════════════════════════════════════
    sec1_h = 18
    fill(colors.HexColor("#1E4D78"))
    pdf.rect(x0, y - sec1_h, content_w, sec1_h, stroke=0, fill=1)
    pdf.setFont(bold, 8.5)
    fill(colors.white)
    pdf.drawString(x0 + 8, y - 12.5, "CONTRACTOR BILL RECONCILIATION")
    pdf.setFont(regular, 6.8)
    pdf.drawRightString(x_end - 8, y - 12.5, f"@ {ra_label}")
    y -= sec1_h

    draw_table_header()

    # ── Row A ──
    table_row("A", f"Total Sub-Contract Bill Value @ {ra_label}",
              amt_total=calc.get("sub_contract_value"), is_bold_label=True)

    # ── Row B ──
    table_row("B", "Add - GST", is_bold_label=True, style="add")
    table_row("", "SGST @ 9%",
              detail=f"SGST @ {calc.get('sgst_rate', 9)}%",
              amt_sub=calc.get("sgst"), indent=16)
    table_row("", "CGST @ 9%",
              detail=f"CGST @ {calc.get('cgst_rate', 9)}%",
              amt_sub=calc.get("cgst"), indent=16)
    table_row("", "Round-off", detail="Round-off",
              amt_total=calc.get("round_off_gst"), indent=16)

    # ── Row C ──
    table_row("C", "Total Amount after GST", detail="A + B",
              amt_total=calc.get("total_after_gst"), style="subtotal")

    # ── Row D ──
    table_row("D", "Less: Deductions", is_bold_label=True, style="deduct")
    table_row("", "SGST TDS @ 1%",
              detail=f"SGST TDS @ {calc.get('sgst_tds_rate', 1)}%",
              amt_sub=calc.get("sgst_tds"), indent=16, style="deduct")
    table_row("", "CGST TDS @ 1%",
              detail=f"CGST TDS @ {calc.get('cgst_tds_rate', 1)}%",
              amt_sub=calc.get("cgst_tds"), indent=16, style="deduct")
    table_row("", "TDS @ 1%",
              detail=f"TDS @ {calc.get('tds_rate', 1)}%",
              amt_sub=calc.get("tds"), indent=16, style="deduct")
    table_row("", "Cess WF @ 1%",
              detail=f"Cess WF @ {calc.get('cess_wf_rate', 1)}%",
              amt_sub=calc.get("cess_wf"), indent=16, style="deduct")
    table_row("", "Total Deductions",
              amt_total=calc.get("total_deductions"),
              indent=16, style="section_total")

    # ── Row E ──
    table_row("E", "Less: ON-HOLD", is_bold_label=True, style="deduct")
    table_row("", "2% Retention",
              detail=f"{calc.get('retention_rate', 2)}% Retention",
              amt_sub=calc.get("retention"), indent=16, style="deduct")
    table_row("", "0.5% @ Testing",
              detail=f"{calc.get('testing_rate', 0.5)}% @ Testing",
              amt_sub=calc.get("testing"), indent=16, style="deduct")
    table_row("", "Total ON-HOLD",
              amt_total=calc.get("total_on_hold"),
              indent=16, style="section_total")
    table_row("", "ROUND-OFF", detail="ROUND-OFF", indent=16)

    # ── Row F ──
    table_row("F", "Net Amount in Rs.", detail="C - D - E",
              amt_total=calc.get("net_amount"), style="grand")

    # ── Row G ──
    table_row("G", "Less: SUB-CONTRACTOR Charges",
              is_bold_label=True, style="deduct")
    table_row("", f"Office Expense @{calc.get('office_expense_rate', 2)}%",
              detail=f"Office Expense @{calc.get('office_expense_rate', 2)}%",
              amt_sub=calc.get("office_expense"), indent=16, style="deduct")
    table_row("", "Total CHARGES",
              amt_total=calc.get("total_charges"),
              indent=16, style="section_total")

    # ── Row H ──
    table_row("H", "Net Sublet Bill from Contractee", detail="C - D - G",
              amt_total=calc.get("net_sublet_bill"), style="grand")

    y -= 12

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 2: SUB-CONTRACTOR PAYMENT CUM INVOICE SUMMARY (I–N)
    # ═══════════════════════════════════════════════════════════════════
    ensure(24)
    sec2_h = 18
    fill(colors.HexColor("#1E4D78"))
    pdf.rect(x0, y - sec2_h, content_w, sec2_h, stroke=0, fill=1)
    pdf.setFont(bold, 8.0)
    fill(colors.white)
    pdf.drawString(x0 + 8, y - 12.5,
                   "SUB-CONTRACTOR'S PAYMENT cum Invoice SUMMARY")
    y -= sec2_h

    draw_table_header()
    row_counter[0] = 0

    # ── Row I ──
    table_row("I", "Total Sublet Bill Value",
              amt_total=calc.get("sublet_bill_value"), is_bold_label=True)

    # ── Row J ──
    table_row("J", "Add - GST", is_bold_label=True, style="add")
    table_row("", "SGST @ 9%",
              detail=f"SGST @ {calc.get('sgst_rate', 9)}%",
              amt_sub=calc.get("sub_sgst"), indent=16)
    table_row("", "CGST @ 9%",
              detail=f"CGST @ {calc.get('cgst_rate', 9)}%",
              amt_sub=calc.get("sub_cgst"), indent=16)
    table_row("", "Round-off", detail="Round-off",
              amt_total=calc.get("sublet_round_off"), indent=16)

    # ── Row K ──
    table_row("K", "Total Amount after GST", detail="I + J",
              amt_total=calc.get("sub_total_after_gst"), style="subtotal")

    # ── Row L ──
    table_row("L", "Less: ON-HOLD", is_bold_label=True, style="deduct")
    table_row("", "2% Retention",
              detail=f"{calc.get('retention_rate', 2)}% Retention",
              amt_sub=calc.get("sub_retention"), indent=16, style="deduct")
    table_row("", "0.5% @ Testing",
              detail=f"{calc.get('testing_rate', 0.5)}% @ Testing",
              amt_sub=calc.get("sub_testing"), indent=16, style="deduct")
    table_row("", "Total ON-HOLD",
              amt_total=calc.get("sub_on_hold"),
              indent=16, style="section_total")

    # ── Row M ──
    table_row("M", "Less: Deductions", is_bold_label=True, style="deduct")
    table_row("", "TDS on Bill Value", detail="TDS on Bill Value",
              amt_sub=calc.get("sub_tds"), indent=16, style="deduct")
    table_row("", "Round-off", detail="Round-off",
              amt_total=calc.get("sublet_tds_round_off"), indent=16)

    # ── Row N ──
    table_row("N", "Net Payable Amount in Rs.", detail="K - L - M",
              amt_total=calc.get("sub_net_payable"), style="grand")

    y -= 10

    # ═══════════════════════════════════════════════════════════════════
    # QUICK SUMMARY PANEL
    # ═══════════════════════════════════════════════════════════════════
    ensure(220)

    panel_x = x0
    panel_w = content_w
    panel_col1 = panel_x + 8          # label start
    panel_col3 = panel_x + panel_w - 8  # amount right-aligned

    # Panel title
    pth = 18
    fill(RIGHT_PANEL_HEADER)
    pdf.rect(panel_x, y - pth, panel_w, pth, stroke=0, fill=1)
    pdf.setFont(bold, 8.5)
    fill(colors.white)
    pdf.drawCentredString(
        panel_x + panel_w / 2, y - 12.5,
        f"QUICK SUMMARY \u2014 {buyer.upper()} CHARGES & B2B BILL")
    y -= pth

    def summary_row(label, amount, style="normal"):
        nonlocal y
        rh = 16
        ensure(rh)

        if style == "header":
            bg, tc = RIGHT_PANEL_HEADER, colors.white
        elif style == "total":
            bg, tc = GRAND_FILL, GRAND_TEXT
        elif style == "subtotal":
            bg, tc = RIGHT_PANEL_TOTAL_BG, BRAND_NAVY
        elif style == "deduct":
            bg, tc = DEDUCT_FILL, TEXT
        elif style == "add":
            bg, tc = ADD_FILL, TEXT
        else:
            bg = RIGHT_PANEL_BG if row_counter[0] % 2 == 0 else colors.white
            tc = TEXT

        fill(bg)
        stroke(GRID_COLOR, 0.3)
        pdf.rect(panel_x, y - rh, panel_w, rh, stroke=1, fill=1)

        mid = panel_x + panel_w / 2
        vline(mid, y, y - rh, GRID_COLOR, 0.3)

        fnt = bold if style in ("total", "subtotal", "header") else regular
        pdf.setFont(fnt, 7.2 if style != "total" else 7.8)
        fill(tc)
        pdf.drawString(panel_col1, y - 11, label)
        if amount is not None:
            pdf.drawRightString(panel_col3, y - 11, fmt_indian(amount))

        y -= rh
        row_counter[0] += 1

    row_counter[0] = 0
    summary_row("Base", calc.get("right_base"))
    summary_row("Add GST @18%", calc.get("right_gst_18"), "add")
    summary_row("TOTAL WITH GST", calc.get("right_total_with_gst"), "subtotal")
    summary_row("SGST (TDS)", calc.get("right_sgst"), "deduct")
    summary_row("CGST (TDS)", calc.get("right_cgst"), "deduct")
    summary_row("IT (TDS)", calc.get("right_it"), "deduct")
    summary_row("1% CESS", calc.get("right_cess"), "deduct")
    summary_row("TOTAL WITH DEDUCTION",
                calc.get("right_total_with_deduction"), "subtotal")
    summary_row(f"{calc.get('retention_rate', 2)}% Retention",
                calc.get("right_retention"), "deduct")
    summary_row(f"{calc.get('testing_rate', 0.5)}% @ Testing",
                calc.get("right_testing"), "deduct")
    summary_row("Net Bill", calc.get("right_net_bill"), "subtotal")
    summary_row(f"Amount to {buyer}",
                calc.get("right_amount_to_sarthi"), "subtotal")

    # Final row: Sarthi Charges | B2B Bill
    final_h = 20
    ensure(final_h)
    fill(GRAND_FILL)
    pdf.rect(panel_x, y - final_h, panel_w, final_h, stroke=0, fill=1)
    mid = panel_x + panel_w / 2
    vline(mid, y, y - final_h, colors.white, 0.5)
    pdf.setFont(bold, 7.5)
    fill(GRAND_TEXT)
    pdf.drawString(panel_col1, y - 8, f"{buyer} Charges")
    pdf.drawRightString(mid - 8, y - 8,
                        fmt_indian(calc.get("right_sarthi_charges")))
    pdf.drawString(mid + 8, y - 8, "B2B Bill")
    pdf.drawRightString(panel_col3, y - 8,
                        fmt_indian(calc.get("right_b2b_bill")))
    net_words = num_to_words_indian(calc.get("sub_net_payable", 0))
    pdf.setFont(regular, 5.8)
    pdf.drawCentredString(panel_x + panel_w / 2, y - 17, net_words)
    y -= final_h

    y -= 12

    # ═══════════════════════════════════════════════════════════════════
    # SIGNATURE BLOCK
    # ═══════════════════════════════════════════════════════════════════
    ensure(68)
    sig_h = 58
    fill(PALE_NAVY)
    stroke(GRID_DARK, 0.6)
    pdf.rect(x0, y - sig_h, content_w, sig_h, stroke=1, fill=1)
    sig_mid = x0 + content_w * 0.6
    vline(sig_mid, y, y - sig_h, GRID_DARK, 0.5)

    # Left: jurisdiction
    pdf.setFont(bold, 7.0)
    fill(TEXT)
    pdf.drawString(x0 + 8, y - 14, "Subject to Ahmedabad Jurisdiction")
    pdf.setFont(regular, 6.5)
    fill(MUTED)
    pdf.drawString(x0 + 8, y - 27, "E. & O. E.")
    pdf.drawString(x0 + 8, y - 39, "This is a computer-generated document.")

    # Right: for contractor
    pdf.setFont(bold, 7.5)
    fill(BRAND_NAVY)
    pdf.drawString(sig_mid + 8, y - 14, f"For {contractor}")
    stamp = _find_stamp(contractor) if include_stamp else None
    if stamp:
        try:
            pdf.drawImage(stamp, x_end - 100, y - 50, width=72, height=34,
                          mask="auto", preserveAspectRatio=True)
        except Exception:
            pass
    pdf.setFont(bold, 7.0)
    fill(TEXT)
    pdf.drawRightString(x_end - 8, y - 48, "Authorised Signatory")
    pdf.setFont(regular, 6.2)
    fill(MUTED)
    pdf.drawRightString(x_end - 8, y - 56, f"GSTIN: {contractor_gstin}")

    y -= sig_h

    page_footer()
    pdf.showPage()
    pdf.save()
    return output_pdf


# ═══════════════════════════════════════════════════════════════════════
# SAMPLE EXECUTION — RA-01 data from PIPLAJ B2B FORMAT.xlsx
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    calc_ra01 = calculate_annexure(
        sub_contract_value=6846845.48,
        sgst_rate=9.0,
        cgst_rate=9.0,
        round_off_gst=-0.67,
        sgst_tds_rate=1.0,
        cgst_tds_rate=1.0,
        tds_rate=1.0,
        cess_wf_rate=1.0,
        retention_rate=2.0,
        testing_rate=0.5,
        office_expense_rate=2.0,
        sublet_bill_value=6482453,
        sublet_round_off=0.46,
        sublet_tds_rate=1.0,
        sublet_tds_round_off=-0.47,
    )

    output = os.path.join(BASE_DIR, "output", "pdf", "annexure_ra01_premium.pdf")
    draw_annexure_pdf({
        "contractor_name": "Jay Khodiyar Enterprise",
        "contractor_gstin": "24BJHPP5061K1ZZ",
        "buyer_name": "Sarthi Construction",
        "buyer_gstin": "24ALRPG2118D1ZI",
        "buyer_address": (
            "228, Vishala Supreme, Opp. Torrent Power Sub-Station, "
            "S P Ring Road, Nikol, Ahmedabad-382350 (GUJARAT)"
        ),
        "buyer_contact_person": "Mr. Sanjaybhai",
        "buyer_mobile": "+91 7600453711",
        "work_name": (
            "Providing Systematic Sewerage Network facility on diff. road "
            "of Piplaj-Gopalpur-Saijpur Gam, Piplaj-survey no-95 and other "
            "Non-T.P. road of this area in Lambha Ward at South Zone of "
            "AMC Area (Package 3)"
        ),
        "invoice_no": "GJ-01",
        "ref_inv_no": "Khodiyar/Piplaj/RA-01/24-25/01",
        "invoice_date": "18th of July, 2024",
        "ref_no": "P-691 Dt: 11-06-2024",
        "ra_bill_label": "RA 01",
        "calculations": calc_ra01,
        "include_stamp": True,
    }, output)
    print(f"Generated: {output}")
