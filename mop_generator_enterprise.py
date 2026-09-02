# -*- coding: utf-8 -*-
"""Billion-Dollar Enterprise Memorandum of Payment (MOP) Vector PDF Engine.

Features:
- Executive corporate branding with high-resolution logo scaling & subtle watermark.
- Prominent 'MEMORANDUM OF PAYMENT' header with document classification badges.
- Dual-card modern information grid for Beneficiary and Statement & Audit metadata.
- Precision institutional financial ledger with letter-coded sections & soft ribbon subtotals.
- Prestigious deep-navy 'NET AMOUNT PAYABLE' grand total showcase box.
- Shaded 'Amount in Words' ribbon with Indian currency phrasing.
- 2-column compliance & digital authorization block with high-res stamp seal.
- Letterhead contact footer with dual-tone geometric brand accent bar.
- Dynamic vertical layout budgeting with multi-page continuation support.
"""

import datetime
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from mop_generator_premium import _find_stamp, calculate_mop, fmt_indian, num_to_words_indian


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "jke_logo_full.png")
LOGO_ICON_PATH = os.path.join(BASE_DIR, "assets", "jke_logo_icon.png")

# Billion-Dollar Enterprise Design Tokens — B&W Print Optimized
PRIMARY_NAVY = colors.HexColor("#071D3B")
SECONDARY_NAVY = colors.HexColor("#0B1B3D")
ACCENT_BLUE = colors.HexColor("#0139C3")
ACCENT_CYAN = colors.HexColor("#38BDF8")
ACCENT_ORANGE = colors.HexColor("#FF6B00")

TEXT_DARK = colors.HexColor("#0F172A")
TEXT_BODY = colors.HexColor("#1E293B")
TEXT_MUTED = colors.HexColor("#555F6D")   # Darker muted for B&W legibility
TEXT_LABEL = colors.HexColor("#3D4654")

BORDER_LIGHT = colors.HexColor("#D0D7E0")  # Slightly darker for B&W visibility
BORDER_MED = colors.HexColor("#B0BAC6")
BORDER_STRONG = colors.HexColor("#071D3B")

CARD_BG = colors.HexColor("#F5F7FA")      # Visible tint in B&W
HEADER_BG = colors.HexColor("#ECF0F5")
SUBTOTAL_BG = colors.HexColor("#E8EEF6")
GRAND_TOTAL_BG = colors.HexColor("#071D3B")
DEDUCT_RED = colors.HexColor("#B91C1C")   # Darker red — prints as dark gray in B&W
WHITE = colors.white


def _wrap(text, font, size, max_width):
    lines, current = [], ""
    for word in str(text or "-").replace("\n", " \n ").split():
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


class EnterpriseMOP:
    """World-Class Enterprise Memorandum of Payment renderer."""

    def __init__(self, pdf, data, calculations):
        self.pdf = pdf
        self.data = data
        self.calc = calculations
        self.pct = calculations.get("pct_config") or {}
        self.page_w, self.page_h = A4
        self.left = 38.0
        self.right = self.page_w - 38.0
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
        self.phone = str(data.get("phone") or "+91 99132 37000")
        self.email = str(data.get("email") or "account@jaykhodiyarenterprise.in")
        self.website = str(data.get("website") or "www.jaykhodiyarenterprise.in")
        self.tagline = str(data.get("tagline") or "INFRASTRUCTURE & ENGINEERING SOLUTIONS")

        # Column X coordinates for financial ledger
        self.x_desc = self.left + 10
        self.x_rate = self.left + 332
        self.x_currency = self.left + 392
        self.x_amount = self.right - 10

    def fill(self, color):
        self.pdf.setFillColor(color)

    def stroke(self, color=BORDER_LIGHT, width=0.5):
        self.pdf.setStrokeColor(color)
        self.pdf.setLineWidth(width)

    def top_accent_bar(self):
        """Draws a crisp dual-tone geometric corporate brand bar at top edge."""
        h = 3.5
        top_y = self.page_h - h
        self.fill(PRIMARY_NAVY)
        self.pdf.rect(0, top_y, self.page_w, h, stroke=0, fill=1)
        
        # Center angled orange transition slash
        x1 = self.page_w * 0.68
        x2 = x1 + 16
        path = self.pdf.beginPath()
        path.moveTo(x1, top_y)
        path.lineTo(x2, top_y)
        path.lineTo(x2 + 8, self.page_h)
        path.lineTo(x1 + 8, self.page_h)
        path.close()
        self.fill(ACCENT_ORANGE)
        self.pdf.drawPath(path, stroke=0, fill=1)

        # Right sapphire blue segment
        path2 = self.pdf.beginPath()
        path2.moveTo(x2, top_y)
        path2.lineTo(self.page_w, top_y)
        path2.lineTo(self.page_w, self.page_h)
        path2.lineTo(x2 + 8, self.page_h)
        path2.close()
        self.fill(ACCENT_BLUE)
        self.pdf.drawPath(path2, stroke=0, fill=1)

    def draw_watermark(self):
        """Draws a faint, prestigious corporate watermark in the page background."""
        watermark_img = LOGO_ICON_PATH if os.path.exists(LOGO_ICON_PATH) else (LOGO_PATH if os.path.exists(LOGO_PATH) else None)
        if not watermark_img:
            return
        try:
            self.pdf.saveState()
            self.pdf.setFillAlpha(0.025)
            wm_w = 260
            wm_h = 260
            wm_x = (self.page_w - wm_w) / 2
            wm_y = (self.page_h - wm_h) / 2 - 20
            image = ImageReader(watermark_img)
            self.pdf.drawImage(image, wm_x, wm_y, wm_w, wm_h, mask="auto", preserveAspectRatio=True)
            self.pdf.restoreState()
        except Exception:
            pass

    def logo(self, x, bottom, max_w=185, max_h=50):
        if not os.path.exists(LOGO_PATH):
            self.pdf.setFont(self.bold, 15)
            self.fill(PRIMARY_NAVY)
            self.pdf.drawString(x, bottom + 15, self.contractor)
            return
        image = ImageReader(LOGO_PATH)
        iw, ih = image.getSize()
        scale = min(max_w / iw, max_h / ih)
        self.pdf.drawImage(image, x, bottom, iw * scale, ih * scale, mask="auto", preserveAspectRatio=True)

    def document_header(self, continuation=False):
        self.page_number += 1
        self.fill(WHITE)
        self.pdf.rect(0, 0, self.page_w, self.page_h, stroke=0, fill=1)
        self.draw_watermark()
        self.top_accent_bar()

        if continuation:
            self.logo(self.left, self.page_h - 62, 160, 42)
            self.pdf.setFont(self.bold, 12)
            self.fill(PRIMARY_NAVY)
            self.pdf.drawRightString(self.right, self.page_h - 40, "MEMORANDUM OF PAYMENT - CONTINUATION")
            self.pdf.setFont(self.regular, 7.5)
            self.fill(TEXT_MUTED)
            self.pdf.drawRightString(self.right, self.page_h - 52, f"REF: {self.ra_no}  •  DATE: {self.ra_date}  •  PAGE {self.page_number}")
            self.stroke(BORDER_LIGHT, 0.6)
            self.pdf.line(self.left, self.page_h - 68, self.right, self.page_h - 68)
            return self.page_h - 82

        # ── Primary Executive Header ──────────────────────────────────────────
        header_bottom = self.page_h - 90
        self.logo(self.left, header_bottom + 8, 195, 52)

        # Right-aligned Title & Document Meta
        self.pdf.setFont(self.bold, 17.5)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawRightString(self.right, self.page_h - 48, "MEMORANDUM OF PAYMENT")

        self.pdf.setFont(self.bold, 7.8)
        self.fill(TEXT_MUTED)
        meta_str = f"GSTIN: {self.contractor_gstin}"
        self.pdf.drawRightString(self.right, self.page_h - 64, meta_str)

        # Elegant separator line
        self.stroke(BORDER_MED, 0.6)
        self.pdf.line(self.left, header_bottom - 2, self.right, header_bottom - 2)

        return header_bottom - 8

    def information_cards(self, top):
        """Draws two executive side-by-side structured corporate cards."""
        card_h = 84
        gap = 10
        card1_w = (self.width - gap) * 0.54
        card2_w = self.width - card1_w - gap
        c1_left = self.left
        c2_left = self.left + card1_w + gap

        # ── Card 1: Beneficiary / Executing Agency ──
        self.fill(CARD_BG)
        self.stroke(BORDER_LIGHT, 0.5)
        self.pdf.roundRect(c1_left, top - card_h, card1_w, card_h, 4, stroke=1, fill=1)
        
        self.fill(HEADER_BG)
        self.pdf.roundRect(c1_left, top - 17, card1_w, 17, 3, stroke=0, fill=1)
        self.stroke(BORDER_LIGHT, 0.5)
        self.pdf.line(c1_left, top - 17, c1_left + card1_w, top - 17)
        self.pdf.setFont(self.bold, 6.8)
        self.fill(TEXT_LABEL)
        self.pdf.drawString(c1_left + 10, top - 12, "BENEFICIARY & EXECUTING AGENCY")

        self.pdf.setFont(self.bold, 9.0)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawString(c1_left + 10, top - 30, self.agency[:42])

        self.pdf.setFont(self.bold, 5.8)
        self.fill(TEXT_MUTED)
        self.pdf.drawString(c1_left + 10, top - 42, "PROJECT / SITE LOCATION")
        wrapped_work = _wrap(self.work, self.regular, 6.8, card1_w - 20)[:2]
        self.pdf.setFont(self.regular, 6.8)
        self.fill(TEXT_BODY)
        wy = top - 52
        for line in wrapped_work:
            self.pdf.drawString(c1_left + 10, wy, line)
            wy -= 8.5
            
        self.pdf.setFont(self.bold, 6.8)
        self.fill(ACCENT_BLUE)
        self.pdf.drawString(c1_left + 10, top - card_h + 8, f"GSTIN: {self.agency_gstin}")

        # ── Card 2: Statement & Audit Reference ──
        self.fill(CARD_BG)
        self.stroke(BORDER_LIGHT, 0.5)
        self.pdf.roundRect(c2_left, top - card_h, card2_w, card_h, 4, stroke=1, fill=1)
        
        self.fill(HEADER_BG)
        self.pdf.roundRect(c2_left, top - 17, card2_w, 17, 3, stroke=0, fill=1)
        self.stroke(BORDER_LIGHT, 0.5)
        self.pdf.line(c2_left, top - 17, c2_left + card2_w, top - 17)
        self.pdf.setFont(self.bold, 6.8)
        self.fill(TEXT_LABEL)
        self.pdf.drawString(c2_left + 10, top - 12, "STATEMENT & AUDIT REFERENCE")

        mid_x = c2_left + (card2_w * 0.48)

        def cell_meta(x, y, label, val, val_color=TEXT_DARK, val_bold=True, val_size=7.8, max_w=95):
            self.pdf.setFont(self.bold, 5.8)
            self.fill(TEXT_MUTED)
            self.pdf.drawString(x, y, label.upper())
            self.pdf.setFont(self.bold if val_bold else self.regular, val_size)
            self.fill(val_color)
            val_str = str(val or "-")
            if stringWidth(val_str, self.bold if val_bold else self.regular, val_size) > max_w:
                while val_str and stringWidth(val_str + "...", self.bold if val_bold else self.regular, val_size) > max_w:
                    val_str = val_str[:-1]
                val_str += "..."
            self.pdf.drawString(x, y - 11, val_str)

        cell_meta(c2_left + 10, top - 32, "RA Bill Reference", self.ra_no, PRIMARY_NAVY, True, 8.8, 105)
        cell_meta(mid_x + 5, top - 32, "Date of Record", self.record_date, TEXT_BODY, True, 8.0, 105)
        cell_meta(c2_left + 10, top - 56, "RA Bill Date", self.ra_date, ACCENT_BLUE, True, 8.0, 105)
        cell_meta(mid_x + 5, top - 56, "Statement Type", "OFFICIAL SETTLEMENT", TEXT_BODY, False, 7.2, 105)

        return top - card_h - 8

    def financial_table_header(self, top):
        h = 18
        self.fill(HEADER_BG)
        self.stroke(BORDER_MED, 0.5)
        self.pdf.rect(self.left, top - h, self.width, h, stroke=1, fill=1)
        self.stroke(PRIMARY_NAVY, 1.0)
        self.pdf.line(self.left, top - h, self.right, top - h)

        self.pdf.setFont(self.bold, 6.8)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawString(self.x_desc, top - 11.5, "PARTICULARS & FINANCIAL BREAKDOWN")
        self.pdf.drawCentredString(self.x_rate, top - 11.5, "RATE / BASIS")
        self.pdf.drawCentredString(self.x_currency, top - 11.5, "REF.")
        self.pdf.drawRightString(self.x_amount, top - 11.5, "AMOUNT (INR)")
        return top - h

    def section_banner(self, y, tag, title):
        """Draws a clean, letter-coded section divider."""
        self.stroke(BORDER_MED, 0.4)
        self.pdf.line(self.left, y, self.right, y)
        self.pdf.setFont(self.bold, 7.8)
        self.fill(PRIMARY_NAVY)
        header_text = f"[{tag}]  {title}" if tag else title
        self.pdf.drawString(self.x_desc, y - 10, header_text)
        return y - 15

    def financial_row(self, y, label, amount, rate="", currency="Rs.", negative=False, addition=False, height=12.8):
        self.pdf.setFont(self.regular, 7.5)
        self.fill(TEXT_BODY)
        self.pdf.drawString(self.x_desc + 12, y - 8.5, label)
        
        self.pdf.setFont(self.regular, 6.8)
        self.fill(TEXT_MUTED)
        if rate:
            self.pdf.drawCentredString(self.x_rate, y - 8.5, rate)
        if currency:
            self.pdf.drawCentredString(self.x_currency, y - 8.5, currency)

        value = float(amount or 0)
        if negative:
            rendered = "-" + fmt_indian(abs(value))
            val_color = DEDUCT_RED
        elif addition:
            rendered = "+" + fmt_indian(abs(value))
            val_color = PRIMARY_NAVY
        else:
            rendered = fmt_indian(value)
            val_color = TEXT_DARK

        self.pdf.setFont(self.regular, 7.6)
        self.fill(val_color)
        self.pdf.drawRightString(self.x_amount, y - 8.5, rendered)
        return y - height

    def subtotal_row(self, y, label, amount, negative=False):
        h = 17
        self.fill(SUBTOTAL_BG)
        self.stroke(BORDER_MED, 0.6)
        self.pdf.rect(self.left, y - h, self.width, h, stroke=1, fill=1)
        # Top border accent for B&W separation
        self.stroke(PRIMARY_NAVY, 0.8)
        self.pdf.line(self.left, y, self.right, y)

        self.pdf.setFont(self.bold, 7.4)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawString(self.x_desc + 5, y - 11.5, label)

        rendered = ("-" if negative else "") + fmt_indian(abs(float(amount or 0)))
        self.pdf.setFont(self.bold, 8.4)
        self.fill(DEDUCT_RED if negative else PRIMARY_NAVY)
        self.pdf.drawRightString(self.x_amount, y - 11.5, rendered)
        return y - h - 3

    def grand_total_showcase(self, y):
        """Draws a clean, B&W-optimized 'NET AMOUNT PAYABLE' showcase card."""
        h = 28
        # Strong border with tinted background — visible in both color and B&W
        self.fill(colors.HexColor("#E8EFF8"))
        self.stroke(PRIMARY_NAVY, 1.2)
        self.pdf.roundRect(self.left, y - h, self.width, h, 3, stroke=1, fill=1)

        # Left solid accent bar (prints as dark gray in B&W)
        self.fill(PRIMARY_NAVY)
        self.pdf.rect(self.left, y - h, 4.0, h, stroke=0, fill=1)

        # Left label group
        self.pdf.setFont(self.bold, 9.2)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawString(self.x_desc + 6, y - 12, "TOTAL NET AMOUNT PAYABLE")
        self.pdf.setFont(self.regular, 5.8)
        self.fill(TEXT_MUTED)
        self.pdf.drawString(self.x_desc + 6, y - 21.5, "Final disbursement authorized post statutory retentions & recoveries")

        # Right amount group
        self.pdf.setFont(self.bold, 8.0)
        self.fill(TEXT_LABEL)
        self.pdf.drawRightString(self.x_amount - 128, y - 18, "INR / Rs.")

        self.pdf.setFont(self.bold, 12.5)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawRightString(self.x_amount, y - 18, fmt_indian(self.calc["net_payable"]))
        return y - h - 5

    def amount_in_words_ribbon(self, top):
        lines = _wrap(self.calc["amount_in_words"], self.bold, 7.0, self.width - 130)[:2]
        h = max(20, 12 + 7.5 * len(lines))
        self.fill(CARD_BG)
        self.stroke(BORDER_LIGHT, 0.5)
        self.pdf.roundRect(self.left, top - h, self.width, h, 3, stroke=1, fill=1)
        
        self.fill(ACCENT_BLUE)
        self.pdf.rect(self.left, top - h, 3, h, stroke=0, fill=1)

        self.pdf.setFont(self.bold, 6.0)
        self.fill(TEXT_MUTED)
        self.pdf.drawString(self.left + 10, top - 10.5, "AMOUNT IN WORDS:")

        self.pdf.setFont(self.bold, 7.0)
        self.fill(PRIMARY_NAVY)
        yy = top - 10.5
        for line in lines:
            self.pdf.drawString(self.left + 115, yy, line)
            yy -= 8.0
        return top - h - 5

    def authorization_panel(self, top):
        """Draws an executive 2-column compliance, verification & digital signature block.

        Layout architecture (right column — all centered):
          1. FOR AND ON BEHALF OF (centered at right_center)
          2. Company name in bold (centered at right_center)
          3. Stamp seal centered in generous dedicated box (zero text overlap)
          4. Signature line (centered at right_center)
          5. AUTHORISED SIGNATORY label (centered at right_center)
          6. CONTRACTOR label (centered at right_center)
        """
        h = 146
        split = self.left + self.width * 0.46

        # Panel borders — strong enough for B&W print
        self.stroke(BORDER_MED, 0.6)
        self.pdf.line(self.left, top, self.right, top)
        self.pdf.line(split, top - 6, split, top - h + 6)
        self.pdf.line(self.left, top - h, self.right, top - h)

        # ── Left Column: Compliance & Legal ──
        self.pdf.setFont(self.bold, 7.5)
        self.fill(TEXT_DARK)
        self.pdf.drawString(self.left + 8, top - 20, "Subject to Ahmedabad Jurisdiction")

        self.pdf.setFont(self.regular, 6.6)
        self.fill(TEXT_MUTED)
        self.pdf.drawString(self.left + 8, top - 38, "E. & O. E.   |   Official Verified Statement")
        self.pdf.drawString(self.left + 8, top - 56, "This is a computer-generated Memorandum of Payment")
        self.pdf.drawString(self.left + 8, top - 69, "issued under authorized corporate accounting and")
        self.pdf.drawString(self.left + 8, top - 82, "billing compliance standards.")

        self.pdf.setFont(self.regular, 6.2)
        self.fill(TEXT_MUTED)
        self.pdf.drawString(self.left + 8, top - 108, "Prepared for financial review, approval and record.")
        self.pdf.drawString(self.left + 8, top - 122, "All disbursements subject to statutory verification.")

        # ── Right Column: Digital Seal & Signatures (All Centered) ──
        right_center = (split + self.right) / 2.0

        self.pdf.setFont(self.bold, 6.5)
        self.fill(TEXT_LABEL)
        self.pdf.drawCentredString(right_center, top - 16, "FOR AND ON BEHALF OF")

        self.pdf.setFont(self.bold, 9.2)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawCentredString(right_center, top - 29, self.contractor)

        # Signature line positioned near the bottom with clear room above
        sign_w = 150
        sign_left = right_center - sign_w / 2
        sign_right = right_center + sign_w / 2
        sign_y = top - h + 26

        self.stroke(PRIMARY_NAVY, 0.75)
        self.pdf.line(sign_left, sign_y, sign_right, sign_y)

        self.pdf.setFont(self.bold, 7.2)
        self.fill(PRIMARY_NAVY)
        self.pdf.drawCentredString(right_center, sign_y - 11, "AUTHORISED SIGNATORY")
        self.pdf.setFont(self.regular, 6.2)
        self.fill(TEXT_MUTED)
        self.pdf.drawCentredString(right_center, sign_y - 20, "CONTRACTOR")

        # Stamp: 96×96 pt, centered in the open vertical space between
        # company name (top - 32) and signature line (sign_y = top - 120), with -3.5° tilt.
        stamp = _find_stamp(self.contractor) if self.data.get("include_stamp", True) else None
        if stamp:
            stamp_w, stamp_h = 96.0, 96.0
            stamp_cx = right_center
            stamp_cy = (top - 32 + sign_y) / 2.0
            try:
                self.pdf.saveState()
                self.pdf.translate(stamp_cx, stamp_cy)
                self.pdf.rotate(-3.5)
                self.pdf.drawImage(
                    stamp,
                    -stamp_w / 2.0,
                    -stamp_h / 2.0,
                    stamp_w,
                    stamp_h,
                    mask="auto",
                    preserveAspectRatio=True,
                )
                self.pdf.restoreState()
            except Exception:
                self.pdf.restoreState()

        return top - h

    def letterhead_footer(self):
        """Draws the bottom contact footer and geometric brand accent bar."""
        y = 34
        self.stroke(BORDER_LIGHT, 0.45)
        self.pdf.line(self.left, y + 10, self.right, y + 10)
        
        self.pdf.setFont(self.regular, 6.5)
        self.fill(TEXT_MUTED)
        contact_str = f"Phone: {self.phone}   •   Email: {self.email}   •   Website: {self.website}"
        self.pdf.drawCentredString(self.page_w / 2, y, contact_str)

        # Bottom dual-tone geometric bar
        h = 3.5
        self.fill(PRIMARY_NAVY)
        self.pdf.rect(0, 0, self.page_w, h, stroke=0, fill=1)
        
        # Center angled orange transition slash
        x1 = self.page_w * 0.65
        x2 = x1 + 16
        path = self.pdf.beginPath()
        path.moveTo(x1, 0)
        path.lineTo(x2, 0)
        path.lineTo(x2 - 8, h)
        path.lineTo(x1 - 8, h)
        path.close()
        self.fill(ACCENT_ORANGE)
        self.pdf.drawPath(path, stroke=0, fill=1)

        # Right sapphire blue
        path2 = self.pdf.beginPath()
        path2.moveTo(x2, 0)
        path2.lineTo(self.page_w, 0)
        path2.lineTo(self.page_w, h)
        path2.lineTo(x2 - 8, h)
        path2.close()
        self.fill(ACCENT_BLUE)
        self.pdf.drawPath(path2, stroke=0, fill=1)

    def render_core_financial_sections(self, y):
        # Section A: Work Value
        y = self.section_banner(y, "A", "WORK VALUE AS PER R.A. BILL")
        y = self.financial_row(y, "Basic Work Amount", self.calc["basic_work"])
        y = self.financial_row(y, "GST on Work Value", self.calc["gross_amount"] - self.calc["basic_work"], "18.00%")
        y = self.subtotal_row(y, "TOTAL WORK DONE AMOUNT AS PER R.A. BILL", self.calc["gross_amount"])

        # Section B: Agency Deductions
        y = self.section_banner(y, "B", "STATUTORY & AGENCY DEDUCTIONS")
        y = self.financial_row(y, "Income Tax / TDS", self.calc["agency_tds"], f"{self.pct.get('agency_tds_pct', 2.0):.2f}%", negative=True)
        y = self.financial_row(y, "SGST TDS", self.calc["agency_sgst"], f"{self.pct.get('agency_sgst_tds_pct', 1.0):.2f}%", negative=True)
        y = self.financial_row(y, "CGST TDS", self.calc["agency_cgst"], f"{self.pct.get('agency_cgst_tds_pct', 1.0):.2f}%", negative=True)
        y = self.subtotal_row(y, "TOTAL AGENCY DEDUCTIONS", self.calc["agency_deductions_total"], negative=True)

        # Section C: Net Work Value & Overheads
        y = self.section_banner(y, "A-B", "NET WORK VALUE & OVERHEAD CHARGES")
        y = self.financial_row(y, "Net Work Done (A - B)", self.calc["net_work_done"])
        y = self.financial_row(y, "Administrative and Head Office Expense", self.calc["admin_expense"], f"{self.pct.get('admin_expense_pct', 3.25):.2f}%", negative=True)

        # Section D: Our Bill Amount Summary
        y = self.section_banner(y, "C", "CONTRACTOR BILL AMOUNT SUMMARY")
        y = self.financial_row(y, "Basic Bill Amount", self.calc["our_basic"])
        y = self.financial_row(y, "SGST", self.calc["our_sgst"], "9.00%")
        y = self.financial_row(y, "CGST", self.calc["our_cgst"], "9.00%")
        y = self.subtotal_row(y, "TOTAL CONTRACTOR GROSS BILL AMOUNT", self.calc["our_bill_gross"])
        return y

    def get_adjustment_rows(self):
        candidates = [
            ("Income Tax (TDS)", self.calc["it_tds"], f"{self.pct.get('it_tds_pct', 1.0):.2f}%", "deduct"),
            ("Retention Money S.D.", self.calc["retention"], f"{self.pct.get('retention_pct', 2.0):.2f}%", "deduct"),
            ("Labour Welfare Cess", self.calc["labour_cess"], f"{self.pct.get('labour_cess_pct', 1.0):.2f}%", "deduct"),
            ("Quality & Testing Fee", self.calc["testing_fee"], f"{self.pct.get('testing_fee_pct', 0.5):.2f}%", "deduct"),
        ]
        rows = [c for c in candidates if abs(c[1]) >= 0.01]
        for row in self.calc.get("custom_adjustments", []):
            rate = f"{row['value']:.2f}%" if row.get("calculation") == "percent" else "FIXED"
            if row.get("amount", 0) > 0:
                rows.append((row["label"], row["amount"], rate, row["operation"]))
        return rows

    def render_adjustments_and_total(self, y, rows):
        y = self.section_banner(y, "D", "FINAL RECOVERIES & ADJUSTMENTS")
        for label, amount, rate, operation in rows:
            y = self.financial_row(
                y,
                label,
                amount,
                rate,
                negative=operation == "deduct",
                addition=operation == "add",
            )
        round_value = float(self.calc.get("round_off") or 0)
        y = self.financial_row(
            y,
            "Round Off",
            abs(round_value),
            "MANUAL" if self.data.get("custom_round_off") is not None else "AUTO",
            negative=round_value < 0,
            addition=round_value > 0,
        )
        return self.grand_total_showcase(y)

    def render(self):
        top = self.document_header(False)
        top = self.information_cards(top)
        y = self.financial_table_header(top)
        y = self.render_core_financial_sections(y)
        rows = self.get_adjustment_rows()

        # Check if all rows + grand total + auth block fit on Page 1 (height budget check)
        needed_height = 17 + (len(rows) + 1) * 14.2 + 35 + 28 + 146 + 25
        if y - needed_height >= 35:
            y = self.render_adjustments_and_total(y, rows)
            words_bottom = self.amount_in_words_ribbon(y)
            self.authorization_panel(words_bottom)
            self.letterhead_footer()
            self.pdf.showPage()
            return

        # Multi-page continuation flow: fill Page 1 with initial rows, then continue
        self.pdf.setFont(self.bold, 7.2)
        self.fill(TEXT_MUTED)
        self.pdf.drawString(self.x_desc, y - 16, "FINAL ADJUSTMENTS CONTINUE ON FOLLOWING PAGE...")
        self.letterhead_footer()
        self.pdf.showPage()

        remaining = list(rows)
        while remaining:
            y = self.document_header(True)
            y = self.financial_table_header(y)
            capacity = 22 if len(remaining) > 22 else len(remaining)
            page_rows, remaining = remaining[:capacity], remaining[capacity:]
            if remaining:
                y = self.section_banner(y, "D", "FINAL ADJUSTMENTS (CONTINUED)")
                for label, amount, rate, operation in page_rows:
                    y = self.financial_row(y, label, amount, rate, negative=operation == "deduct", addition=operation == "add", height=15.5)
                self.letterhead_footer()
                self.pdf.showPage()
                continue
            
            y = self.render_adjustments_and_total(y, page_rows)
            words_bottom = self.amount_in_words_ribbon(y)
            self.authorization_panel(words_bottom)
            self.letterhead_footer()
            self.pdf.showPage()


def draw_mop_pdf(mop_data, output_pdf):
    """Entrypoint: Generate Memorandum of Payment Vector PDF."""
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)
    calculations = mop_data.get("calculations") or calculate_mop(
        mop_data.get("amount", 0),
        mop_data.get("config"),
        mop_data.get("custom_round_off"),
        mop_data.get("custom_adjustments"),
    )
    pdf = canvas.Canvas(output_pdf, pagesize=A4)
    EnterpriseMOP(pdf, mop_data, calculations).render()
    pdf.save()
    return output_pdf


__all__ = ["calculate_mop", "draw_mop_pdf"]
