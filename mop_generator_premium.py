# -*- coding: utf-8 -*-
"""Premium branded A4 Memorandum of Payment generator.

Matches the formal accounting-table design language:
- Bordered 3-column metadata box
- "MEMORANDUM OF PAYMENT" executive header with contractor GSTIN
- 4-column financial table: DESCRIPTION | RATE | REF. | AMOUNT (Rs.)
- Letter-coded sections: (A) WORK VALUE, (B) AGENCY DEDUCTIONS, (A-B) NET WORK VALUE, etc.
- Soft-blue subtotal bands with highlighted blue amounts
- Full multi-page continuation support for dynamic adjustments
"""

import datetime
import os
from typing import Dict, Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "jke_logo_full.png")

# Brand & Enterprise Design Tokens
BRAND_BLUE = colors.HexColor("#0139C3")
BRAND_BLUE_DARK = colors.HexColor("#002B99")
BRAND_NAVY = colors.HexColor("#071D3B")
TEXT = colors.HexColor("#101D33")
MUTED = colors.HexColor("#526176")
BORDER = colors.HexColor("#D4DCE8")
PALE_BLUE = colors.HexColor("#F3F7FC")
PALE_NAVY = colors.HexColor("#F7F8FA")
PALE_GREEN = colors.HexColor("#EAF8F3")
GREEN = colors.HexColor("#167D61")
PALE_RED = colors.HexColor("#FFF3F2")
RED = colors.HexColor("#B84B43")
WHITE = colors.white


def fmt_indian(value):
    """Format a number with Indian digit grouping and two decimals."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "0.00")
    negative = number < 0
    integer, decimal = f"{abs(number):.2f}".split(".")
    if len(integer) > 3:
        tail = integer[-3:]
        head = integer[:-3]
        pairs = []
        while len(head) > 2:
            pairs.insert(0, head[-2:])
            head = head[:-2]
        if head:
            pairs.insert(0, head)
        integer = ",".join(pairs + [tail])
    result = f"{integer}.{decimal}"
    return f"-{result}" if negative else result


ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digits(number):
    if number < 20:
        return ONES[number]
    return TENS[number // 10] + ((" " + ONES[number % 10]) if number % 10 else "")


def _three_digits(number):
    hundreds, remainder = divmod(number, 100)
    parts = []
    if hundreds:
        parts.append(ONES[hundreds] + " Hundred")
    if remainder:
        parts.append(_two_digits(remainder))
    return " ".join(parts)


def num_to_words_indian(value):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return ""
    if number == 0:
        return "Zero Rupees Only"
    if number < 0:
        return "Minus " + num_to_words_indian(abs(number))
    crore, number = divmod(number, 10_000_000)
    lakh, number = divmod(number, 100_000)
    thousand, number = divmod(number, 1_000)
    parts = []
    if crore:
        parts.append(_two_digits(crore) + " Crore")
    if lakh:
        parts.append(_two_digits(lakh) + " Lakh")
    if thousand:
        parts.append(_two_digits(thousand) + " Thousand")
    if number:
        parts.append(_three_digits(number))
    return " ".join(parts) + " Rupees Only"


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_adjustments(rows: Iterable[Dict], bases: Dict[str, float]):
    normalized = []
    for index, raw in enumerate(list(rows or [])[:30]):
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or f"Custom adjustment {index + 1}").strip()[:90]
        operation = str(raw.get("operation") or raw.get("type") or "deduct").lower().strip()
        operation = "add" if operation in {"add", "addition", "+"} else "deduct"
        calculation = str(raw.get("calculation") or raw.get("mode") or "fixed").lower().strip()
        calculation = "percent" if calculation in {"percent", "percentage", "%"} else "fixed"
        base_key = str(raw.get("base") or "gross_amount").lower().strip()
        if base_key not in bases:
            base_key = "gross_amount"
        value = max(0.0, _number(raw.get("value"), 0.0))
        amount = bases[base_key] * value / 100.0 if calculation == "percent" else value
        normalized.append({
            "label": label,
            "operation": operation,
            "calculation": calculation,
            "base": base_key,
            "value": value,
            "amount": amount,
            "str_amount": fmt_indian(amount),
        })
    return normalized


def calculate_mop(gross_amount, config=None, custom_round_off=None, custom_adjustments=None):
    """Calculate the full MOP, including arbitrary final additions/deductions."""
    cfg = config or {}
    gross = max(0.0, _number(gross_amount))

    pcts = {
        "agency_tds_pct": _number(cfg.get("agency_tds_pct"), 2.0),
        "agency_sgst_tds_pct": _number(cfg.get("agency_sgst_tds_pct"), 1.0),
        "agency_cgst_tds_pct": _number(cfg.get("agency_cgst_tds_pct"), 1.0),
        "admin_expense_pct": _number(cfg.get("admin_expense_pct"), 3.25),
        "it_tds_pct": _number(cfg.get("it_tds_pct"), 1.0),
        "retention_pct": _number(cfg.get("retention_pct"), 2.0),
        "labour_cess_pct": _number(cfg.get("labour_cess_pct"), 1.0),
        "testing_fee_pct": _number(cfg.get("testing_fee_pct"), 0.5),
    }

    basic_work = gross / 1.18 if gross else 0.0
    agency_tds = basic_work * pcts["agency_tds_pct"] / 100.0
    agency_sgst = basic_work * pcts["agency_sgst_tds_pct"] / 100.0
    agency_cgst = basic_work * pcts["agency_cgst_tds_pct"] / 100.0
    agency_deductions_total = agency_tds + agency_sgst + agency_cgst
    net_work_done = gross - agency_deductions_total

    admin_expense = gross * pcts["admin_expense_pct"] / 100.0
    our_bill_gross = net_work_done - admin_expense
    our_basic = our_bill_gross / 1.18 if our_bill_gross > 0 else 0.0
    our_sgst = our_basic * 0.09
    our_cgst = our_basic * 0.09

    it_tds = our_basic * pcts["it_tds_pct"] / 100.0
    retention = gross * pcts["retention_pct"] / 100.0
    labour_cess = basic_work * pcts["labour_cess_pct"] / 100.0
    testing_fee = gross * pcts["testing_fee_pct"] / 100.0

    bases = {
        "gross_amount": gross,
        "basic_work": basic_work,
        "net_work_done": net_work_done,
        "our_bill_gross": our_bill_gross,
        "our_basic": our_basic,
    }
    adjustments = _normalize_adjustments(custom_adjustments, bases)
    custom_additions = sum(row["amount"] for row in adjustments if row["operation"] == "add")
    custom_deductions = sum(row["amount"] for row in adjustments if row["operation"] == "deduct")

    core_deductions = it_tds + retention + labour_cess + testing_fee
    raw_net = our_bill_gross - core_deductions + custom_additions - custom_deductions
    if custom_round_off is None:
        net_payable = float(round(raw_net))
        round_off = net_payable - raw_net
    else:
        round_off = _number(custom_round_off)
        net_payable = round(raw_net + round_off, 2)

    values = {
        "gross_amount": gross,
        "basic_work": basic_work,
        "agency_tds": agency_tds,
        "agency_sgst": agency_sgst,
        "agency_cgst": agency_cgst,
        "agency_deductions_total": agency_deductions_total,
        "net_work_done": net_work_done,
        "admin_expense": admin_expense,
        "our_bill_gross": our_bill_gross,
        "our_basic": our_basic,
        "our_sgst": our_sgst,
        "our_cgst": our_cgst,
        "it_tds": it_tds,
        "retention": retention,
        "labour_cess": labour_cess,
        "testing_fee": testing_fee,
        "core_deductions_total": core_deductions,
        "custom_additions_total": custom_additions,
        "custom_deductions_total": custom_deductions,
        "round_off": round_off,
        "net_payable": net_payable,
    }
    result = dict(values)
    result["pct_config"] = pcts
    result["custom_adjustments"] = adjustments
    for key, value in values.items():
        result[f"str_{key}"] = (f"{value:+.2f}" if key == "round_off" and value else fmt_indian(value))
    result["amount_in_words"] = num_to_words_indian(net_payable)
    return result


def _wrap(text, font, size, max_width):
    words = str(text or "-").replace("\n", " \n ").split()
    lines, current = [], ""
    for word in words:
        if word == "\n":
            lines.append(current or " ")
            current = ""
            continue
        candidate = word if not current else current + " " + word
        if not current or stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or ["-"]


def _find_stamp(contractor):
    stamps_dir = os.path.join(BASE_DIR, "Stamps")
    if not os.path.isdir(stamps_dir):
        return None
    tokens = [token.lower() for token in str(contractor).split()[:2]]
    for filename in os.listdir(stamps_dir):
        if filename.lower().endswith(".png") and any(token in filename.lower() for token in tokens):
            return os.path.join(stamps_dir, filename)
    return None


class MOPRenderer:
    """Renders the formal accounting MOP PDF on standard A4."""

    def __init__(self, pdf, data, calculations):
        self.pdf = pdf
        self.data = data
        self.calc = calculations
        self.pct = calculations["pct_config"]
        self.page_w, self.page_h = A4
        self.left, self.right = 40.0, self.page_w - 40.0
        self.width = self.right - self.left
        self.regular, self.bold = "Helvetica", "Helvetica-Bold"
        self.page_number = 0

        self.contractor = str(data.get("contractor_name") or "Jay Khodiyar Enterprise")
        self.contractor_gstin = str(data.get("contractor_gstin") or "24BJHPP5061K1ZZ")
        self.agency = str(data.get("agency_name") or "-")
        self.agency_gstin = str(data.get("agency_gstin") or "-")
        self.work = str(data.get("work_name") or data.get("project_description") or "-")
        self.bill_no = str(data.get("bill_sr_no") or "-")
        self.record_date = str(data.get("date_of_record") or datetime.date.today().strftime("%d/%m/%Y"))
        self.ra_no = str(data.get("ra_bill_no") or "-")
        self.ra_date = str(data.get("ra_bill_date") or self.record_date)
        self.include_stamp = bool(data.get("include_stamp", True))
        self.phone = str(data.get("phone") or "9913237000")
        self.email = str(data.get("email") or "account@jaykhodiyarenterprise.in")
        self.website = str(data.get("website") or "www.jaykhodiyarenterprise.in")

        # Column X coordinates
        self.x_desc = self.left + 9
        self.x_rate = self.left + 333
        self.x_currency = self.left + 390
        self.x_amount = self.right - 9

    def fill(self, color):
        self.pdf.setFillColor(color)

    def stroke(self, color=BORDER, width=0.5):
        self.pdf.setStrokeColor(color)
        self.pdf.setLineWidth(width)

    def logo(self, x, bottom, max_w=190, max_h=56):
        if os.path.exists(LOGO_PATH):
            try:
                image = ImageReader(LOGO_PATH)
                iw, ih = image.getSize()
                scale = min(max_w / iw, max_h / ih)
                self.pdf.drawImage(image, x, bottom, iw * scale, ih * scale, mask="auto", preserveAspectRatio=True)
                return
            except Exception:
                pass
        # Clean vector logo fallback
        scale = 1.0
        icon = 30 * scale
        self.fill(BRAND_BLUE)
        self.pdf.circle(x + 7 * scale, bottom + max_h - 7 * scale, 4.4 * scale, stroke=0, fill=1)
        self.fill(BRAND_NAVY)
        p = self.pdf.beginPath()
        top_icon = bottom + max_h
        p.moveTo(x, top_icon - 19 * scale)
        p.curveTo(x + 8 * scale, top_icon - 10 * scale, x + 19 * scale, top_icon - 10 * scale, x + icon, top_icon - 18 * scale)
        p.curveTo(x + 18 * scale, top_icon - 21 * scale, x + 8 * scale, top_icon - 27 * scale, x + 1 * scale, top_icon - 31 * scale)
        p.curveTo(x - 2 * scale, top_icon - 27 * scale, x - 2 * scale, top_icon - 22 * scale, x, top_icon - 19 * scale)
        self.pdf.drawPath(p, stroke=0, fill=1)
        tx = x + icon + 6 * scale
        self.pdf.setFont(self.bold, 13 * scale)
        self.fill(BRAND_BLUE)
        self.pdf.drawString(tx, top_icon - 10 * scale, "JAY")
        self.pdf.setFont(self.bold, 11 * scale)
        self.fill(BRAND_NAVY)
        self.pdf.drawString(tx, top_icon - 23 * scale, "KHODIYAR")
        self.pdf.setFont(self.bold, 4.8 * scale)
        self.pdf.drawString(tx, top_icon - 31 * scale, "E N T E R P R I S E")

    def document_header(self, continuation=False):
        self.page_number += 1
        self.fill(WHITE)
        self.pdf.rect(0, 0, self.page_w, self.page_h, stroke=0, fill=1)
        self.fill(BRAND_BLUE)
        self.pdf.rect(0, self.page_h - 3, self.page_w, 3, stroke=0, fill=1)

        if continuation:
            self.logo(self.left, self.page_h - 65, 116, 34)
            self.pdf.setFont(self.bold, 11)
            self.fill(BRAND_NAVY)
            self.pdf.drawRightString(self.right, self.page_h - 42, "MEMORANDUM OF PAYMENT - CONTINUED")
            self.pdf.setFont(self.regular, 7)
            self.fill(MUTED)
            self.pdf.drawRightString(self.right, self.page_h - 56, f"{self.ra_no}  |  {self.ra_date}")
            self.stroke(BORDER, 0.6)
            self.pdf.line(self.left, self.page_h - 74, self.right, self.page_h - 74)
            return self.page_h - 91

        self.logo(self.left, self.page_h - 95, 190, 56)
        self.pdf.setFont(self.bold, 17.5)
        self.fill(BRAND_NAVY)
        self.pdf.drawRightString(self.right, self.page_h - 55, "MEMORANDUM OF PAYMENT")
        self.pdf.setFont(self.bold, 7.5)
        self.fill(MUTED)
        self.pdf.drawRightString(self.right, self.page_h - 73, f"DATE: {self.record_date}  |  GSTIN: {self.contractor_gstin}")
        return self.page_h - 100

    def information_panel(self, top):
        h = 111
        self.fill(WHITE)
        self.stroke(BORDER, 0.55)
        self.pdf.rect(self.left, top - h, self.width, h, stroke=1, fill=1)
        c1, c2 = self.left + 252, self.left + 409
        self.pdf.line(c1, top, c1, top - h)
        self.pdf.line(c2, top, c2, top - h)
        self.pdf.line(c1, top - 51, self.right, top - 51)

        def item(x, y, label, value, box_w, value_color=TEXT, lines=1, size=8.2):
            self.pdf.setFont(self.bold, 6.5)
            self.fill(MUTED)
            self.pdf.drawString(x, y, label.upper())
            wrapped = _wrap(value, self.bold, size, box_w)[:lines]
            self.pdf.setFont(self.bold, size)
            self.fill(value_color)
            yy = y - 15
            for line in wrapped:
                self.pdf.drawString(x, yy, line)
                yy -= size + 4

        item(self.left + 13, top - 16, "Name of Agency", self.agency, 226, BRAND_BLUE, 1, 8.4)
        item(self.left + 13, top - 57, "Name of Work", self.work, 226, TEXT, 3, 7.5)
        item(c1 + 13, top - 16, "GST No.", self.agency_gstin, 130, BRAND_BLUE, 1, 7.8)
        item(c1 + 13, top - 67, "Sr. No. of the Bill", self.bill_no, 130, TEXT, 1, 8.2)
        item(c2 + 13, top - 16, "Date of Record", self.record_date, 92, TEXT, 1, 8.2)
        item(c2 + 13, top - 67, "RA Bill No.", self.ra_no, 92, TEXT, 2, 7.3)
        return top - h

    def section_header(self, top, title="MEMORANDUM OF PAYMENT"):
        h = 20
        self.fill(PALE_BLUE)
        self.stroke(BORDER, 0.55)
        self.pdf.rect(self.left, top - h, self.width, h, stroke=1, fill=1)

        # Brand blue left bar
        self.fill(BRAND_BLUE)
        self.pdf.rect(self.left, top - h, 6, h, stroke=0, fill=1)

        # Small angled slash detail
        for offset in (0, 5):
            path = self.pdf.beginPath()
            x = self.left + 326 + offset
            path.moveTo(x, top)
            path.lineTo(x + 12, top - h)
            path.lineTo(x + 15, top - h)
            path.lineTo(x + 3, top)
            path.close()
            self.fill(BRAND_BLUE if offset == 0 else colors.HexColor("#7E9ED6"))
            self.pdf.drawPath(path, stroke=0, fill=1)

        self.stroke(BRAND_NAVY, 0.7)
        self.pdf.line(self.left, top - h, self.right, top - h)
        self.pdf.setFont(self.bold, 9.6)
        self.fill(BRAND_NAVY)
        self.pdf.drawString(self.left + 15, top - 13.5, title)
        return top - h

    def financial_columns(self, top):
        h = 16
        self.fill(PALE_NAVY)
        self.stroke(BORDER, 0.45)
        self.pdf.rect(self.left, top - h, self.width, h, stroke=1, fill=1)
        self.pdf.setFont(self.bold, 6.5)
        self.fill(MUTED)
        self.pdf.drawString(self.x_desc, top - 10.7, "DESCRIPTION")
        self.pdf.drawCentredString(self.x_rate, top - 10.7, "RATE")
        self.pdf.drawCentredString(self.x_currency, top - 10.7, "REF.")
        self.pdf.drawRightString(self.x_amount, top - 10.7, "AMOUNT (Rs.)")
        return top - h

    def rule(self, y, strong=False):
        self.stroke(BRAND_NAVY if strong else BORDER, 0.8 if strong else 0.4)
        self.pdf.line(self.left, y, self.right, y)

    def financial_section(self, y, marker, title):
        self.rule(y, True)
        self.pdf.setFont(self.bold, 8.3)
        self.fill(BRAND_NAVY)
        self.pdf.drawString(self.x_desc, y - 13, f"{marker}  {title}" if marker else title)
        return y - 19

    def financial_row(self, y, label, amount, rate="", currency="Rs.", negative=False, addition=False, height=13):
        self.pdf.setFont(self.regular, 7.8)
        self.fill(TEXT)
        self.pdf.drawString(self.x_desc + 13, y - 9, label)
        self.pdf.setFont(self.regular, 7.2)
        self.fill(MUTED)
        if rate:
            self.pdf.drawCentredString(self.x_rate, y - 9, rate)
        if currency:
            self.pdf.drawCentredString(self.x_currency, y - 9, currency)
        value = float(amount or 0)
        if negative:
            rendered = "-" + fmt_indian(abs(value))
        elif addition:
            rendered = "+" + fmt_indian(abs(value))
        else:
            rendered = fmt_indian(value)
        self.pdf.setFont(self.regular, 7.9)
        self.fill(TEXT)
        self.pdf.drawRightString(self.x_amount, y - 9, rendered)
        return y - height

    def subtotal(self, y, label, amount, negative=False):
        h = 20
        self.fill(PALE_BLUE)
        self.stroke(BORDER, 0.65)
        self.pdf.rect(self.left, y - h, self.width, h, stroke=1, fill=1)
        self.pdf.setFont(self.bold, 7.7)
        self.fill(BRAND_NAVY)
        self.pdf.drawString(self.x_desc, y - 13, label)
        rendered = ("-" if negative else "") + fmt_indian(abs(float(amount or 0)))
        self.pdf.setFont(self.bold, 8.7)
        self.fill(BRAND_BLUE)
        self.pdf.drawRightString(self.x_amount, y - 13, rendered)
        return y - h

    def grand_total(self, y):
        h = 29
        self.fill(PALE_BLUE)
        self.pdf.rect(self.left, y - h, self.width, h, stroke=0, fill=1)
        self.stroke(BRAND_NAVY, 0.9)
        self.pdf.line(self.left, y, self.right, y)
        self.pdf.line(self.left, y - h, self.right, y - h)
        self.pdf.setFont(self.bold, 10.2)
        self.fill(BRAND_NAVY)
        self.pdf.drawString(self.x_desc, y - 19, "NET AMOUNT PAYABLE")
        self.pdf.setFont(self.bold, 7.8)
        self.pdf.drawRightString(self.x_amount - 126, y - 19, "Rs.")
        self.pdf.setFont(self.bold, 12.0)
        self.fill(BRAND_BLUE)
        self.pdf.drawRightString(self.x_amount, y - 19, fmt_indian(self.calc["net_payable"]))
        return y - h

    def amount_in_words(self, top):
        lines = _wrap(self.calc["amount_in_words"], self.bold, 7.2, self.width - 112)[:2]
        h = max(27, 17 + 8 * len(lines))
        self.fill(PALE_BLUE)
        self.stroke(BORDER, 0.45)
        self.pdf.rect(self.left, top - h, self.width, h, stroke=1, fill=1)
        self.pdf.setFont(self.bold, 6.4)
        self.fill(MUTED)
        self.pdf.drawString(self.left + 9, top - 12, "AMOUNT IN WORDS")
        self.pdf.setFont(self.bold, 7.2)
        self.fill(TEXT)
        yy = top - 12
        for line in lines:
            self.pdf.drawString(self.left + 105, yy, line)
            yy -= 8
        return top - h

    def authorization(self, top, compact=False):
        natural_top = top
        if natural_top >= 154:
            panel_top = 154
            panel_h = 102
            compact = False
        else:
            panel_top = natural_top
            panel_h = min(102, max(58, panel_top - 45))
            compact = panel_h < 90
        panel_bottom = panel_top - panel_h
        split = self.left + self.width * 0.52

        self.stroke(BORDER, 0.5)
        self.pdf.line(self.left, panel_top, self.right, panel_top)
        self.pdf.line(split, panel_top - 7, split, panel_bottom + 5)
        self.pdf.line(self.left, panel_bottom, self.right, panel_bottom)

        # Left Column: Legal / Jurisdiction
        self.pdf.setFont(self.bold, 7.1 if compact else 7.4)
        self.fill(TEXT)
        self.pdf.drawString(self.left, panel_top - (14 if compact else 19), "Subject to Ahmedabad Jurisdiction")
        self.pdf.setFont(self.regular, 6.4 if compact else 6.7)
        self.fill(MUTED)
        self.pdf.drawString(self.left, panel_top - (29 if compact else 37), "E. & O. E.")
        self.pdf.drawString(self.left, panel_top - (41 if compact else 50), "This is a computer-generated Memorandum of Payment.")
        if not compact:
            self.pdf.drawString(self.left, panel_top - 63, "Prepared for financial review, approval and record.")

        # Right Column: Company Auth
        auth_left = split + 15
        self.pdf.setFont(self.bold, 6.0 if compact else 6.3)
        self.fill(MUTED)
        self.pdf.drawString(auth_left, panel_top - (13 if compact else 14), "FOR AND ON BEHALF OF")
        self.pdf.setFont(self.bold, 7.5 if compact else 8.0)
        self.fill(BRAND_BLUE)
        self.pdf.drawString(auth_left, panel_top - (25 if compact else 29), self.contractor)

        stamp = _find_stamp(self.contractor) if self.include_stamp else None
        if compact:
            stamp_x, stamp_y, stamp_w, stamp_h = auth_left + 2, panel_bottom + 4, 40, 40
            line_left = auth_left + 55
            line_y = panel_bottom + 23
            sign_size, role_size = 6.2, 5.9
            sign_offset, role_offset = 9, 17
        else:
            stamp_x, stamp_y, stamp_w, stamp_h = auth_left + 3, panel_bottom + 5, 62, 62
            line_left = auth_left + 82
            line_y = panel_bottom + 34
            sign_size, role_size = 6.8, 6.3
            sign_offset, role_offset = 11, 21

        if stamp:
            try:
                self.pdf.drawImage(stamp, stamp_x, stamp_y, stamp_w, stamp_h, mask="auto", preserveAspectRatio=True)
            except Exception:
                pass

        line_right = self.right - 8
        self.stroke(BRAND_NAVY, 0.65)
        self.pdf.line(line_left, line_y, line_right, line_y)
        centre = (line_left + line_right) / 2
        self.pdf.setFont(self.bold, sign_size)
        self.fill(TEXT)
        self.pdf.drawCentredString(centre, line_y - sign_offset, "AUTHORISED SIGNATORY")
        self.pdf.setFont(self.regular, role_size)
        self.fill(MUTED)
        self.pdf.drawCentredString(centre, line_y - role_offset, "CONTRACTOR")
        return panel_bottom

    def footer(self):
        y = 32
        self.stroke(BORDER, 0.45)
        self.pdf.line(self.left, y + 10, self.right, y + 10)
        self.pdf.setFont(self.regular, 6.5)
        self.fill(MUTED)
        self.pdf.drawString(self.left, y, self.phone)
        self.pdf.drawCentredString((self.left + self.right) / 2, y, self.email)
        self.pdf.drawRightString(self.right, y, self.website)
        self.fill(BRAND_NAVY)
        self.pdf.rect(0, 0, self.page_w, 2, stroke=0, fill=1)
        self.fill(BRAND_BLUE)
        self.pdf.rect(0, 0, self.page_w * 0.36, 2, stroke=0, fill=1)

    def core_sections(self, y):
        y = self.financial_columns(y)
        y = self.financial_section(y, "(A)", "WORK VALUE")
        y = self.financial_row(y, "Basic Amount", self.calc["basic_work"])
        y = self.financial_row(y, "GST", self.calc["gross_amount"] - self.calc["basic_work"], "18.00%")
        y = self.subtotal(y, "TOTAL WORK DONE AMOUNT AS PER R.A. BILL", self.calc["gross_amount"])

        y -= 5
        y = self.financial_section(y, "(B)", "AGENCY DEDUCTIONS")
        y = self.financial_row(y, "Income Tax / TDS", self.calc["agency_tds"], f"{self.pct['agency_tds_pct']:.2f}%", negative=True)
        y = self.financial_row(y, "SGST TDS", self.calc["agency_sgst"], f"{self.pct['agency_sgst_tds_pct']:.2f}%", negative=True)
        y = self.financial_row(y, "CGST TDS", self.calc["agency_cgst"], f"{self.pct['agency_cgst_tds_pct']:.2f}%", negative=True)
        y = self.subtotal(y, "TOTAL AGENCY DEDUCTIONS", self.calc["agency_deductions_total"], negative=True)

        y -= 5
        y = self.financial_section(y, "(A-B)", "NET WORK VALUE")
        y = self.financial_row(y, "Net work done (A-B)", self.calc["net_work_done"])
        y = self.financial_row(y, "Administrative and head expense", self.calc["admin_expense"], f"{self.pct['admin_expense_pct']:.2f}%", negative=True)

        y -= 5
        y = self.financial_section(y, "", "OUR BILL AMOUNT")
        y = self.financial_row(y, "Basic", self.calc["our_basic"])
        y = self.financial_row(y, "SGST", self.calc["our_sgst"], "9.00%")
        y = self.financial_row(y, "CGST", self.calc["our_cgst"], "9.00%")
        y = self.subtotal(y, "TOTAL OUR BILL AMOUNT", self.calc["our_bill_gross"])
        return y

    def final_rows(self):
        rows = [
            ("Income Tax (TDS)", self.calc["it_tds"], f"{self.pct['it_tds_pct']:.2f}%", "deduct"),
            ("Retention Money S.D.", self.calc["retention"], f"{self.pct['retention_pct']:.2f}%", "deduct"),
            ("Labour Cess", self.calc["labour_cess"], f"{self.pct['labour_cess_pct']:.2f}%", "deduct"),
            ("Testing Fee", self.calc["testing_fee"], f"{self.pct['testing_fee_pct']:.2f}%", "deduct"),
        ]
        for row in self.calc.get("custom_adjustments", []):
            rate = f"{row['value']:.2f}%" if row["calculation"] == "percent" else "FIXED"
            rows.append((row["label"], row["amount"], rate, row["operation"]))
        return rows

    def final_adjustments(self, y, rows):
        y -= 5
        y = self.financial_section(y, "", "FINAL ADJUSTMENTS")
        for label, amount, rate, operation in rows:
            y = self.financial_row(
                y,
                label,
                amount,
                rate,
                negative=operation == "deduct",
                addition=operation == "add",
            )
        round_value = float(self.calc["round_off"] or 0)
        y = self.financial_row(y, "Round Off", abs(round_value), "MANUAL" if self.data.get("custom_round_off") is not None else "AUTO", negative=round_value < 0, addition=round_value > 0)
        return self.grand_total(y)

    def render(self):
        top = self.document_header(False)
        top = self.information_panel(top)
        y = self.section_header(top - 12)
        y = self.core_sections(y)
        rows = self.final_rows()

        # 4 standard adjustments fit perfectly on Page 1
        if len(rows) <= 5:
            y = self.final_adjustments(y, rows)
            words_bottom = self.amount_in_words(y - 7)
            self.authorization(words_bottom - 2)
            self.footer()
            self.pdf.showPage()
            return

        # More than 5 adjustments: Continue onto Page 2
        self.pdf.setFont(self.bold, 7.2)
        self.fill(MUTED)
        self.pdf.drawString(self.x_desc, y - 18, "FINAL ADJUSTMENTS CONTINUE ON THE FOLLOWING PAGE")
        self.footer()
        self.pdf.showPage()

        remaining = list(rows)
        while remaining:
            y = self.document_header(True)
            y = self.section_header(y, "FINAL ADJUSTMENTS")
            y = self.financial_columns(y)
            capacity = 24 if len(remaining) > 24 else len(remaining)
            page_rows, remaining = remaining[:capacity], remaining[capacity:]
            if remaining:
                for label, amount, rate, operation in page_rows:
                    y = self.financial_row(y, label, amount, rate, negative=operation == "deduct", addition=operation == "add", height=18)
                self.footer()
                self.pdf.showPage()
                continue
            y = self.final_adjustments(y + 5, page_rows)
            words_bottom = self.amount_in_words(y - 9)
            self.authorization(words_bottom - 3)
            self.footer()
            self.pdf.showPage()


def draw_mop_pdf(mop_data, output_pdf):
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)
    calculations = mop_data.get("calculations") or calculate_mop(
        mop_data.get("amount", 0),
        mop_data.get("config"),
        mop_data.get("custom_round_off"),
        mop_data.get("custom_adjustments"),
    )
    pdf = canvas.Canvas(output_pdf, pagesize=A4)
    MOPRenderer(pdf, mop_data, calculations).render()
    pdf.save()
    return output_pdf


if __name__ == "__main__":
    sample = calculate_mop(
        52050841,
        config={
            "agency_tds_pct": 2.0,
            "agency_sgst_tds_pct": 1.0,
            "agency_cgst_tds_pct": 1.0,
            "admin_expense_pct": 3.25,
            "it_tds_pct": 1.0,
            "retention_pct": 2.0,
            "labour_cess_pct": 1.0,
            "testing_fee_pct": 0.5,
        }
    )
    output = os.path.join(BASE_DIR, "output", "pdf", "premium_mop_standard.pdf")
    draw_mop_pdf({
        "contractor_name": "Jay Khodiyar Enterprise",
        "contractor_gstin": "24BJHPP5061K1ZZ",
        "agency_name": "YOGI CONSTRUCTION CO.",
        "agency_gstin": "24AAAFY3044N1Z1",
        "work_name": "CONSTRUCTION OF STORM WATER DRAIN FROM MAHALAXMI LAKE TO ROPADA LAKE IN VATVA WARD OF SOUTH ZONE IN AMC AREA (PHASE-2)",
        "bill_sr_no": "19/26-27",
        "date_of_record": "24/08/2026",
        "ra_bill_no": "RA BILL NO. 07 (Vatva)",
        "ra_bill_date": "24/08/2026",
        "calculations": sample,
        "include_stamp": True,
    }, output)
    print(f"Generated: {output}")
