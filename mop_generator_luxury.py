# -*- coding: utf-8 -*-
"""Reference-matched premium A4 Memorandum of Payment renderer.

The presentation mirrors the approved JKE concept while keeping text, amounts,
wrapping, custom adjustments, and page continuation deterministic and vector.
"""

import datetime
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from mop_generator_premium import _find_stamp, calculate_mop, fmt_indian


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "jke_logo_full.png")
ICON_PATH = os.path.join(BASE_DIR, "assets", "jke_logo_icon.png")

BLUE = colors.HexColor("#0758C9")
ROYAL = colors.HexColor("#003E9E")
NAVY = colors.HexColor("#071D3A")
INK = colors.HexColor("#0A1B36")
MUTED = colors.HexColor("#52647A")
LINE = colors.HexColor("#B8CBE4")
PALE = colors.HexColor("#F1F6FC")
PALE_2 = colors.HexColor("#E9F1FA")
RED = colors.HexColor("#C93636")
GREEN = colors.HexColor("#15705B")
WHITE = colors.white


def _wrap(text, font, size, width):
    words = str(text or "-").replace("\n", " \n ").split()
    lines, current = [], ""
    for word in words:
        if word == "\n":
            lines.append(current or " ")
            current = ""
            continue
        trial = word if not current else current + " " + word
        if stringWidth(trial, font, size) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or ["-"]


def draw_mop_pdf(mop_data, output_pdf):
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)
    pdf = canvas.Canvas(output_pdf, pagesize=A4)
    pw, ph = A4
    regular, bold = "Helvetica", "Helvetica-Bold"
    left, right = 20.0, pw - 20.0
    width = right - left

    contractor = str(mop_data.get("contractor_name") or "Jay Khodiyar Enterprise")
    contractor_gstin = str(mop_data.get("contractor_gstin") or "-")
    agency = str(mop_data.get("agency_name") or "-")
    agency_gstin = str(mop_data.get("agency_gstin") or "-")
    work_name = str(mop_data.get("work_name") or mop_data.get("project_description") or "-")
    bill_no = str(mop_data.get("bill_sr_no") or "-")
    record_date = str(mop_data.get("date_of_record") or datetime.date.today().strftime("%d/%m/%Y"))
    ra_no = str(mop_data.get("ra_bill_no") or "-")
    ra_date = str(mop_data.get("ra_bill_date") or record_date)
    include_stamp = bool(mop_data.get("include_stamp", True))
    phone = str(mop_data.get("phone") or "+91 97147 37000")
    email = str(mop_data.get("email") or "info@jaykhodiyarenterprise.com")
    website = str(mop_data.get("website") or "www.jaykhodiyarenterprise.com")
    calc = mop_data.get("calculations") or calculate_mop(
        mop_data.get("amount", 0),
        mop_data.get("config"),
        mop_data.get("custom_round_off"),
        mop_data.get("custom_adjustments"),
    )
    pct = calc["pct_config"]
    custom = list(calc.get("custom_adjustments") or [])
    page_no = 0

    def set_fill(color):
        pdf.setFillColor(color)

    def set_stroke(color=LINE, width_=0.55):
        pdf.setStrokeColor(color)
        pdf.setLineWidth(width_)

    def logo(x, y, max_w=224, max_h=72):
        if os.path.exists(LOGO_PATH):
            im = ImageReader(LOGO_PATH)
            iw, ih = im.getSize()
            scale = min(max_w / iw, max_h / ih)
            pdf.drawImage(im, x, y, iw * scale, ih * scale, mask="auto", preserveAspectRatio=True)

    def icon_person(x, y):
        set_stroke(BLUE, 0.85)
        pdf.circle(x + 5, y + 9, 3.5, stroke=1, fill=0)
        pdf.arc(x, y, x + 10, y + 8, 0, 180)

    def icon_building(x, y):
        set_stroke(BLUE, 0.75)
        pdf.rect(x + 1, y, 9, 14, stroke=1, fill=0)
        for dx in (3, 6, 9):
            pdf.line(x + dx, y + 3, x + dx, y + 5)
            pdf.line(x + dx, y + 8, x + dx, y + 10)

    def icon_calendar(x, y):
        set_stroke(BLUE, 0.8)
        pdf.roundRect(x, y, 13, 13, 1.5, stroke=1, fill=0)
        pdf.line(x, y + 9, x + 13, y + 9)
        pdf.line(x + 3, y + 11, x + 3, y + 15)
        pdf.line(x + 10, y + 11, x + 10, y + 15)

    def field(x, top, label, value, max_w, icon_fn=None, value_size=8.4, max_lines=3):
        if icon_fn:
            icon_fn(x, top - 20)
            tx = x + 24
        else:
            tx = x
        pdf.setFont(regular, 7.1)
        set_fill(INK)
        pdf.drawString(tx, top - 8, label)
        lines = _wrap(value, bold, value_size, max_w - (tx - x))[:max_lines]
        pdf.setFont(bold, value_size)
        set_fill(ROYAL if max_lines == 1 else INK)
        yy = top - 21
        for line in lines:
            pdf.drawString(tx, yy, line)
            yy -= value_size + 4

    def base_page(continuation=False):
        nonlocal page_no
        page_no += 1
        set_fill(WHITE)
        pdf.rect(0, 0, pw, ph, stroke=0, fill=1)
        set_fill(BLUE)
        pdf.rect(0, ph - 8, pw, 8, stroke=0, fill=1)
        set_fill(NAVY)
        pdf.rect(pw * 0.62, ph - 8, pw * 0.38, 8, stroke=0, fill=1)
        set_stroke(LINE, 0.45)
        pdf.rect(3, 4, pw - 6, ph - 8, stroke=1, fill=0)
        if continuation:
            logo(left + 8, ph - 65, 126, 41)
            pdf.setFont(bold, 12.5)
            set_fill(NAVY)
            pdf.drawRightString(right - 8, ph - 36, "MEMORANDUM OF PAYMENT")
            pdf.setFont(regular, 7.2)
            pdf.drawRightString(right - 8, ph - 49, f"CONTINUED  |  {ra_no}  |  {ra_date}")
            return ph - 78

        logo(left + 12, ph - 104, 224, 72)
        pdf.setFont(bold, 17.0)
        set_fill(NAVY)
        pdf.drawRightString(right - 14, ph - 68, "MEMORANDUM OF PAYMENT")
        pdf.setFont(bold, 7.5)
        set_fill(MUTED)
        pdf.drawRightString(right - 14, ph - 85, f"DATE: {record_date}  |  GSTIN: {contractor_gstin}")

        info_top, info_h = ph - 116, 112
        set_fill(WHITE)
        set_stroke(LINE, 0.55)
        pdf.roundRect(left, info_top - info_h, width, info_h, 5, stroke=1, fill=1)
        c1, c2 = left + 253, left + 421
        pdf.line(c1, info_top - 15, c1, info_top - info_h + 13)
        pdf.line(c2, info_top - 15, c2, info_top - info_h + 13)
        field(left + 15, info_top - 10, "Name of Agency", agency, 222, icon_person, 8.5, 1)
        field(left + 15, info_top - 57, "Name of Work", work_name, 222, icon_building, 7.7, 3)
        field(c1 + 17, info_top - 10, "GST No.", agency_gstin, 135, icon_building, 8.0, 1)
        field(c1 + 17, info_top - 60, "Sr. No. of the Bill", bill_no, 135, icon_building, 8.4, 1)
        field(c2 + 17, info_top - 10, "Date of Record", record_date, 105, icon_calendar, 8.4, 1)

        strip_top = info_top - info_h - 9
        set_fill(WHITE)
        set_stroke(LINE, 0.55)
        pdf.roundRect(left, strip_top - 27, width, 27, 5, stroke=1, fill=1)
        pdf.setFont(regular, 7.6)
        set_fill(INK)
        pdf.drawCentredString(left + width / 6, strip_top - 17, ra_no)
        pdf.drawCentredString(left + width / 2, strip_top - 17, f"DATE : {ra_date}")
        pdf.drawCentredString(left + width * 5 / 6, strip_top - 17, f"GST NO.: {contractor_gstin}")
        set_stroke(MUTED, 0.4)
        pdf.line(left + width / 3, strip_top - 7, left + width / 3, strip_top - 21)
        pdf.line(left + width * 2 / 3, strip_top - 7, left + width * 2 / 3, strip_top - 21)
        return strip_top - 39

    def title_bar(top, text="MEMORANDUM OF PAYMENT"):
        set_fill(NAVY)
        pdf.roundRect(left, top - 22, width, 22, 4, stroke=0, fill=1)
        set_fill(BLUE)
        pdf.roundRect(left, top - 22, 315, 22, 4, stroke=0, fill=1)
        set_fill(colors.HexColor("#78A6E6"))
        for offset in (0, 8, 16):
            p = pdf.beginPath()
            x = left + 300 + offset
            p.moveTo(x, top)
            p.lineTo(x + 15, top - 22)
            p.lineTo(x + 20, top - 22)
            p.lineTo(x + 5, top)
            p.close()
            pdf.drawPath(p, stroke=0, fill=1)
        pdf.setFont(bold, 10.7)
        set_fill(WHITE)
        pdf.drawString(left + 17, top - 15, text)
        return top - 22

    def frame(top, bottom):
        set_stroke(LINE, 0.6)
        set_fill(WHITE)
        pdf.roundRect(left, bottom, width, top - bottom, 5, stroke=1, fill=1)

    def section_label(y, marker, title):
        pdf.setFont(bold, 13 if marker else 8)
        set_fill(ROYAL)
        if marker:
            pdf.drawString(left + 12, y, marker)
            pdf.setFont(bold, 8.2)
            set_fill(INK)
            pdf.drawString(left + 74, y + 1, title)
        else:
            pdf.drawCentredString((left + right) / 2, y, title)

    def money(value, x=right - 18, y=0, color=INK, bold_=False, signed=False):
        amount = float(value or 0)
        text = fmt_indian(abs(amount))
        if signed and amount:
            text = ("+" if amount > 0 else "-") + text
        pdf.setFont(bold if bold_ else regular, 8.4 if not bold_ else 9.3)
        set_fill(color)
        pdf.drawRightString(x, y, text)

    def detail_row(y, label, amount, basis="", deduct=False, add=False, label_x=None):
        lx = label_x or left + 75
        pdf.setFont(regular, 8.0)
        set_fill(INK)
        pdf.drawString(lx, y, label)
        if basis:
            pdf.setFont(regular, 7.4)
            set_fill(MUTED)
            pdf.drawCentredString(right - 190, y, basis)
        color = RED if deduct else (GREEN if add else INK)
        money(-amount if deduct else amount, y=y, color=color, signed=deduct or add)

    def subtotal(y, label, amount, dark=False, deduct=False):
        if dark:
            set_fill(NAVY)
            pdf.rect(left + 10, y - 15, width - 20, 25, stroke=0, fill=1)
            pdf.setFont(bold, 10.2)
            set_fill(WHITE)
            pdf.drawString(left + 68, y - 6, label)
            set_fill(WHITE)
            pdf.rect(right - 137, y - 15, 127, 25, stroke=0, fill=1)
            pdf.setFont(bold, 12.0)
            set_fill(ROYAL)
            pdf.drawRightString(right - 18, y - 6, "Rs. " + fmt_indian(amount))
            return
        set_fill(PALE)
        set_stroke(LINE, 0.45)
        pdf.roundRect(left + 10, y - 13, width - 20, 24, 3, stroke=1, fill=1)
        pdf.setFont(bold, 8.2)
        set_fill(ROYAL if not deduct else RED)
        pdf.drawString(left + 18, y - 5, label)
        money(-amount if deduct else amount, y=y - 5, color=RED if deduct else ROYAL, bold_=True, signed=deduct)

    def footer():
        y = 18
        set_stroke(LINE, 0.45)
        pdf.line(left + 8, y + 15, right - 8, y + 15)
        pdf.setFont(regular, 6.8)
        set_fill(INK)
        pdf.drawString(left + 34, y, phone)
        pdf.drawCentredString((left + right) / 2, y, email)
        pdf.drawRightString(right - 22, y, website)
        pdf.setFont(bold, 8)
        set_fill(BLUE)
        pdf.drawString(left + 20, y - 1, "TEL")
        pdf.drawCentredString((left + right) / 2 - 85, y - 1, "MAIL")
        pdf.drawRightString(right - 170, y - 1, "WEB")

    def signature_words(y):
        set_fill(PALE)
        set_stroke(LINE, 0.45)
        pdf.roundRect(left + 10, y - 24, width - 20, 24, 3, stroke=1, fill=1)
        pdf.setFont(bold, 7.6)
        set_fill(ROYAL)
        pdf.drawString(left + 22, y - 15, "AMOUNT IN WORDS")
        word_lines = _wrap(calc["amount_in_words"], bold, 7.1, width - 150)[:2]
        pdf.setFont(bold, 7.1)
        tx = left + 112
        for i, line in enumerate(word_lines):
            pdf.drawString(tx, y - 15 - i * 8, line)
        sig_top = y - 31
        pdf.setFont(bold, 8.0)
        set_fill(INK)
        pdf.drawString(left + 10, sig_top - 8, "For :")
        set_fill(ROYAL)
        pdf.drawString(left + 33, sig_top - 8, contractor)
        stamp = _find_stamp(contractor) if include_stamp else None
        if stamp:
            try:
                pdf.drawImage(stamp, left + 34, sig_top - 51, 66, 38, mask="auto", preserveAspectRatio=True)
            except Exception:
                pass
        set_stroke(NAVY, 0.55)
        pdf.line(left + 20, sig_top - 53, left + 116, sig_top - 53)
        pdf.setFont(regular, 6.6)
        set_fill(INK)
        pdf.drawCentredString(left + 68, sig_top - 62, "Authorised Signatory")
        pdf.setFont(bold, 6.7)
        set_fill(ROYAL)
        pdf.drawCentredString(left + 68, sig_top - 71, "Contractor")
        if os.path.exists(ICON_PATH):
            try:
                pdf.saveState()
                pdf.setFillAlpha(0.05)
                pdf.drawImage(ICON_PATH, right - 115, sig_top - 82, 72, 72, mask="auto", preserveAspectRatio=True)
                pdf.restoreState()
            except Exception:
                pass

    def standard_page():
        top = base_page(False)
        body_top = title_bar(top)
        frame(body_top, 42)
        y = body_top - 27

        section_label(y, "(A)", "WORK VALUE")
        detail_row(y - 14, "Basic Amount", calc["basic_work"])
        detail_row(y - 27, "GST", calc["gross_amount"] - calc["basic_work"], "18%")
        subtotal(y - 43, "Total work done amount as per R A Bill", calc["gross_amount"])
        set_stroke(LINE, 0.35)
        pdf.line(left + 10, y - 62, right - 10, y - 62)

        y -= 72
        section_label(y, "(B)", "AGENCY DEDUCTIONS")
        detail_row(y - 14, "Less :   Income Tax / TDS", calc["agency_tds"], f"{pct['agency_tds_pct']:.2f}%", deduct=True, label_x=left + 12)
        detail_row(y - 27, "Less :   SGST TDS", calc["agency_sgst"], f"{pct['agency_sgst_tds_pct']:.2f}%", deduct=True, label_x=left + 12)
        detail_row(y - 40, "Less :   CGST TDS", calc["agency_cgst"], f"{pct['agency_cgst_tds_pct']:.2f}%", deduct=True, label_x=left + 12)
        subtotal(y - 56, "TOTAL AGENCY DEDUCTIONS", calc["agency_deductions_total"], deduct=True)

        y -= 76
        section_label(y, "(A-B)", "NET WORK VALUE")
        detail_row(y - 14, "Net work done (A-B)", calc["net_work_done"])
        detail_row(y - 28, "Administrative and head expense", calc["admin_expense"], f"{pct['admin_expense_pct']:.2f}%", deduct=True)

        y -= 42
        set_stroke(LINE, 0.45)
        pdf.line(left + 10, y + 10, right - 10, y + 10)
        section_label(y, "", "OUR BILL AMOUNT")
        box_left, box_mid, box_right = left + 15, left + 275, right - 15
        row_h = 13
        set_stroke(NAVY, 0.45)
        for i, (lab, val, rate) in enumerate((
            ("BASIC", calc["our_basic"], ""),
            ("SGST @9%", calc["our_sgst"], "9%"),
            ("CGST @9%", calc["our_cgst"], "9%"),
        )):
            yy = y - 7 - i * row_h
            pdf.rect(box_left, yy - row_h, box_mid - box_left, row_h, stroke=1, fill=0)
            pdf.rect(box_mid, yy - row_h, box_right - box_mid, row_h, stroke=1, fill=0)
            pdf.setFont(regular, 7.3)
            set_fill(INK)
            pdf.drawCentredString((box_left + box_mid) / 2, yy - 10, lab)
            money(val, x=box_right - 9, y=yy - 10)
        subtotal(y - 54, "GROSS BILL AMOUNT", calc["our_bill_gross"])

        y -= 68
        final_rows = [
            ("Income Tax (TDS)", calc["it_tds"], f"{pct['it_tds_pct']:.2f}%", "deduct"),
            ("Retention Money S.D.", calc["retention"], f"{pct['retention_pct']:.2f}%", "deduct"),
            ("Labour Cess", calc["labour_cess"], f"{pct['labour_cess_pct']:.2f}%", "deduct"),
            ("Testing Fee", calc["testing_fee"], f"{pct['testing_fee_pct']:.2f}%", "deduct"),
        ]
        final_rows.extend((row["label"], row["amount"], (f"{row['value']:.2f}%" if row["calculation"] == "percent" else "Fixed"), row["operation"]) for row in custom)

        available = y - 154
        if len(final_rows) * 14 <= available:
            pdf.setFont(bold, 7.6)
            set_fill(ROYAL)
            pdf.drawString(left + 12, y, "FINAL DEDUCTIONS / ADJUSTMENTS")
            yy = y - 17
            for label, amount, rate, operation in final_rows:
                detail_row(yy, "Less :   " + label if operation == "deduct" else "Add :   " + label, amount, rate, deduct=operation == "deduct", add=operation == "add", label_x=left + 12)
                yy -= 14
            detail_row(yy, "Round off", calc["round_off"], "Manual" if mop_data.get("custom_round_off") is not None else "Auto", add=calc["round_off"] >= 0, deduct=calc["round_off"] < 0, label_x=left + 300)
            subtotal(yy - 23, "NET AMOUNT PAYABLE", calc["net_payable"], dark=True)
            signature_words(yy - 48)
            footer()
            pdf.showPage()
            return

        # Many custom fields: close page one cleanly and continue the final ledger.
        pdf.setFont(bold, 8.2)
        set_fill(ROYAL)
        pdf.drawCentredString((left + right) / 2, y - 12, "FINAL DEDUCTIONS / ADJUSTMENTS CONTINUE ON PAGE 2")
        footer()
        pdf.showPage()
        continuation_page(final_rows)

    def continuation_page(rows):
        top = base_page(True)
        body_top = title_bar(top, "FINAL DEDUCTIONS / ADJUSTMENTS")
        frame(body_top, 42)
        y = body_top - 28
        set_fill(PALE_2)
        pdf.rect(left + 10, y - 18, width - 20, 18, stroke=0, fill=1)
        pdf.setFont(bold, 7.2)
        set_fill(NAVY)
        pdf.drawString(left + 20, y - 12, "PARTICULARS")
        pdf.drawCentredString(right - 190, y - 12, "BASIS / RATE")
        pdf.drawRightString(right - 18, y - 12, "AMOUNT (Rs.)")
        y -= 35
        for index, (label, amount, rate, operation) in enumerate(rows):
            if y < 185:
                footer()
                pdf.showPage()
                top = base_page(True)
                body_top = title_bar(top, "FINAL ADJUSTMENTS - CONTINUED")
                frame(body_top, 42)
                y = body_top - 32
            detail_row(y, "Less :   " + label if operation == "deduct" else "Add :   " + label, amount, rate, deduct=operation == "deduct", add=operation == "add", label_x=left + 20)
            set_stroke(LINE, 0.25)
            pdf.line(left + 12, y - 6, right - 12, y - 6)
            y -= 20
        detail_row(y, "Round off", calc["round_off"], "Manual" if mop_data.get("custom_round_off") is not None else "Auto", add=calc["round_off"] >= 0, deduct=calc["round_off"] < 0, label_x=left + 300)
        subtotal(y - 28, "NET AMOUNT PAYABLE", calc["net_payable"], dark=True)
        signature_words(y - 55)
        footer()
        pdf.showPage()

    standard_page()
    pdf.save()
    return output_pdf


__all__ = ["calculate_mop", "draw_mop_pdf"]

