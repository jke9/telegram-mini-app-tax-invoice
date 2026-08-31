#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JNP Infrastructure Personalised Invoice Generator (Telegram Mini App Module)
=============================================================================
Generates 100% vector ReportLab PDF Tax / Proforma Invoices matching
the exact personalized JNP layout from 'Jnp invoice Formate Example.pdf'.

Features:
- Fixed Buyer (Bill to) section with clean vertical text wrapping (NO text overlaps!).
- Exact 1-to-1 visual layout matching 'Jnp invoice Formate Example.pdf'.
- JNP Infrastructure (GJ) company header, Surat address, MSME UDYAM registration.
- Dual-column Seller vs Metadata grid layout.
- Work Order description header block.
- 8-column items table (Sl No, Description of Services, HSN/SAC, GST Rate, Quantity, Rate, per, Amount).
- CGST (9%), SGST (9%), Less: Round Off, Total Amount.
- Exact Indian Currency Words without commas or hyphens.
- Comprehensive HSN/SAC GST summary breakdown table (HSN/SAC, Taxable Value, CGST Rate/Amt, SGST/UTGST Rate/Amt, Total Tax Amount).
- DCB Bank Surat account details, PAN, and Surat Jurisdiction footer declaration.
"""

import os
import sys
import random
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    from num2words import num2words
except ImportError:
    num2words = None

PAGE_W, PAGE_H = 595.0, 842.0

# Register standard Arial TTF fonts
try:
    pdfmetrics.registerFont(TTFont('Arial',           'C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Bold',      'C:/Windows/Fonts/arialbd.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Italic',    'C:/Windows/Fonts/ariali.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-BoldItalic','C:/Windows/Fonts/arialbi.ttf'))
    R, B, RI, BI = 'Arial', 'Arial-Bold', 'Arial-Italic', 'Arial-BoldItalic'
except Exception:
    R, B, RI, BI = 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique'


def format_currency(val):
    """Indian numbering format style (e.g. 1,66,58,209.41 or 1,96,56,687.00)."""
    try:
        fval = float(val)
        is_negative = fval < 0
        fval = abs(fval)
        
        s = f"{fval:.2f}"
        int_part, dec_part = s.split(".")
        
        if len(int_part) <= 3:
            res_int = int_part
        else:
            last3 = int_part[-3:]
            rest = int_part[:-3]
            groups = []
            while len(rest) > 2:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.insert(0, rest)
            res_int = ",".join(groups) + "," + last3
            
        formatted = f"{res_int}.{dec_part}"
        return f"(-){formatted}" if is_negative else formatted
    except (ValueError, TypeError):
        return str(val or "")


def amount_to_clean_words_indian(amount):
    """Converts numeric amount into Indian Currency Words matching JNP PDF example (no commas/hyphens)."""
    if num2words:
        try:
            int_val = int(amount)
            dec_val = int(round((amount - int_val) * 100))
            
            words_int = num2words(int_val, lang='en_IN').title()
            words_int = words_int.replace('-', ' ').replace(',', '').replace(' And ', ' ').replace(' and ', ' ').strip()
            words_int = " ".join(words_int.split())
            
            if dec_val > 0:
                words_dec = num2words(dec_val, lang='en_IN').lower()
                words_dec = words_dec.replace('-', ' ').replace(',', '').replace(' and ', ' ').strip()
                words_dec = " ".join(words_dec.split())
                return f"INR {words_int} and {words_dec} paise Only"
            else:
                return f"INR {words_int} Only"
        except Exception:
            pass
    return f"INR {format_currency(amount)} Only"


def wrap_text_to_max_width(c, text, max_width_pt, font_name, font_size):
    """Wraps text string into a list of lines fitting strictly within max_width_pt."""
    c.setFont(font_name, font_size)
    words = str(text).replace(',', ', ').split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        if c.stringWidth(test_line, font_name, font_size) <= max_width_pt:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def draw_jnp_invoice_pdf(data_dict, output_pdf_path):
    """
    Generates a 100% vector ReportLab PDF matching 'Jnp invoice Formate Example.pdf' 1-to-1.
    """
    c = canvas.Canvas(output_pdf_path, pagesize=A4)
    c.setLineWidth(0.5)
    c.setStrokeColor(black)
    
    # Outer Margin Bounds (x=37.0 to x=558.0 pt matching JNP PDF layout)
    M_LEFT = 37.0
    M_RIGHT = 558.0
    M_TOP = 810.0
    
    W = M_RIGHT - M_LEFT  # 521.0 pt
    
    # -------------------------------------------------------------
    # 1. TOP TITLE BAR
    # -------------------------------------------------------------
    title_text = data_dict.get("invoice_title", "Proforma Invoice")
    c.setFont(B, 11)
    c.drawCentredString(PAGE_W / 2.0, M_TOP - 12, title_text)
    
    Y_CUR = M_TOP - 18 # 792.0 pt
    
    # -------------------------------------------------------------
    # 2. SELLER & METADATA GRID (2 Columns)
    # -------------------------------------------------------------
    GRID_Y_TOP = Y_CUR
    GRID_Y_BOT = Y_CUR - 165.0
    MID_X = M_LEFT + 245.0 # 282.0 pt matching JNP reference PDF
    
    c.rect(M_LEFT, GRID_Y_BOT, W, GRID_Y_TOP - GRID_Y_BOT)
    c.line(MID_X, GRID_Y_BOT, MID_X, GRID_Y_TOP)
    
    # Left Box: Seller (JNP Infrastructure (GJ)) Details
    c.setFont(B, 10)
    c.drawString(M_LEFT + 6, GRID_Y_TOP - 14, "JNP Infrastructure (GJ)")
    
    c.setFont(R, 8.5)
    seller_lines = [
        "303 - Union Trade Center",
        "B/s Apple Hospital",
        "Udhana Darwaja",
        "Surat",
        "MSME NO. UDYAM-GJ-22-0004969",
        "GSTIN/UIN: 24AADFJ3113C1Z6",
        "State Name :  Gujarat, Code : 24",
        "Contact : 0261- 4800808,+91-6356666808",
        "E-Mail : jnpprojects@gmail.com"
    ]
    y_s = GRID_Y_TOP - 26
    for line in seller_lines:
        if "MSME" in line or "GSTIN" in line:
            c.setFont(B, 8.5)
        else:
            c.setFont(R, 8.5)
        c.drawString(M_LEFT + 6, y_s, line)
        y_s -= 11.5
        
    # Right Box: Metadata Fields
    x_r_mid = MID_X + 120.0 # 402.0 pt
    
    r_h1 = GRID_Y_TOP - 32
    r_h2 = GRID_Y_TOP - 64
    r_h3 = GRID_Y_TOP - 96
    r_h4 = GRID_Y_TOP - 128
    
    c.line(MID_X, r_h1, M_RIGHT, r_h1)
    c.line(MID_X, r_h2, M_RIGHT, r_h2)
    c.line(MID_X, r_h3, M_RIGHT, r_h3)
    c.line(MID_X, r_h4, M_RIGHT, r_h4)
    
    c.line(x_r_mid, r_h1, x_r_mid, GRID_Y_TOP)
    c.line(x_r_mid, r_h3, x_r_mid, r_h2)
    
    # Meta Row 1
    c.setFont(R, 7.5)
    c.drawString(MID_X + 4, GRID_Y_TOP - 10, "Invoice No.")
    c.setFont(B, 8.5)
    c.drawString(MID_X + 4, GRID_Y_TOP - 22, str(data_dict.get("invoice_no", "PROFORMA-1")))
    
    c.setFont(R, 7.5)
    c.drawString(x_r_mid + 4, GRID_Y_TOP - 10, "Dated")
    c.setFont(B, 8.5)
    c.drawString(x_r_mid + 4, GRID_Y_TOP - 22, str(data_dict.get("invoice_date", "30-Jun-26")))
    
    # Meta Row 2
    c.setFont(R, 7.5)
    c.drawString(MID_X + 4, r_h1 - 10, "Delivery Note")
    c.drawString(MID_X + 4, r_h1 - 22, str(data_dict.get("delivery_note", "")))
    
    c.drawString(x_r_mid + 4, r_h1 - 10, "Mode/Terms of Payment")
    c.drawString(x_r_mid + 4, r_h1 - 22, str(data_dict.get("payment_terms", "")))
    
    # Meta Row 3
    c.setFont(R, 7.5)
    c.drawString(MID_X + 4, r_h2 - 10, "Reference No. & Date.")
    c.setFont(B, 8)
    c.drawString(MID_X + 4, r_h2 - 22, str(data_dict.get("reference_no_date", "CHILODA RA 1  dt. 30-Jun-26")))
    
    c.setFont(R, 7.5)
    c.drawString(x_r_mid + 4, r_h2 - 10, "Other References")
    c.drawString(x_r_mid + 4, r_h2 - 22, str(data_dict.get("other_references", "")))
    
    # Meta Row 4
    c.setFont(R, 7.5)
    c.drawString(MID_X + 4, r_h3 - 10, "Buyer’s Order No.")
    c.drawString(MID_X + 4, r_h3 - 22, str(data_dict.get("buyer_order_no", "")))
    
    c.drawString(x_r_mid + 4, r_h3 - 10, "Dated")
    c.drawString(x_r_mid + 4, r_h3 - 22, str(data_dict.get("order_date", "30-Jun-26")))
    
    # Meta Row 5
    c.setFont(R, 7.5)
    c.drawString(MID_X + 4, r_h4 - 10, "Dispatch Doc No.")
    c.drawString(MID_X + 4, r_h4 - 22, str(data_dict.get("dispatch_doc_no", "")))
    
    c.drawString(x_r_mid + 4, r_h4 - 10, "Delivery Note Date")
    c.drawString(x_r_mid + 4, r_h4 - 22, str(data_dict.get("delivery_note_date", "")))
    
    Y_CUR = GRID_Y_BOT # 627.0 pt
    
    # -------------------------------------------------------------
    # 3. BUYER (BILL TO) & WORK ORDER SECTION (FIXED NO OVERLAP)
    # -------------------------------------------------------------
    raw_addr_input = data_dict.get("customer_address_lines", [
        "Sardar Patel Bhavan,",
        "Finance Department,",
        "Danapith,",
        "Ahamedabad Gpo",
        "Ahmedabad"
    ])
    
    parsed_addr_lines = []
    if isinstance(raw_addr_input, list):
        for item in raw_addr_input:
            parsed_addr_lines.extend(wrap_text_to_max_width(c, item, 235.0, R, 8))
    else:
        parsed_addr_lines.extend(wrap_text_to_max_width(c, str(raw_addr_input), 235.0, R, 8))
        
    buyer_name = data_dict.get("customer_name", "Ahmedabad Municipal Corporation")
    buyer_name_lines = wrap_text_to_max_width(c, buyer_name, 235.0, B, 8.5)
    
    total_text_lines = len(buyer_name_lines) + len(parsed_addr_lines) + 3
    BUYER_H = max(115.0, 24.0 + (total_text_lines * 10.5))
    BUYER_Y_BOT = Y_CUR - BUYER_H
    
    c.rect(M_LEFT, BUYER_Y_BOT, W, BUYER_H)
    c.line(MID_X, BUYER_Y_BOT, MID_X, Y_CUR)
    
    # Left: Buyer (Bill to) Header & Staked Text
    y_b = Y_CUR - 11.0
    c.setFont(R, 7.5)
    c.drawString(M_LEFT + 6, y_b, "Buyer (Bill to)")
    y_b -= 11.0
    
    c.setFont(B, 8.5)
    for b_l in buyer_name_lines:
        c.drawString(M_LEFT + 6, y_b, b_l)
        y_b -= 10.5
        
    c.setFont(R, 8)
    for a_l in parsed_addr_lines:
        c.drawString(M_LEFT + 6, y_b, a_l)
        y_b -= 10.0
        
    # Vertical stacking of GSTIN, PAN, State Name under address matching JNP reference PDF
    c.setFont(R, 8)
    gstin_str = str(data_dict.get('customer_gstin', '24AAALA0024C3Z7'))
    pan_str = str(data_dict.get('customer_pan', 'AAALA0024C'))
    state_str = str(data_dict.get('customer_state', 'Gujarat, Code : 24'))
    
    c.drawString(M_LEFT + 6, y_b, "GSTIN/UIN")
    c.drawString(M_LEFT + 75, y_b, f": {gstin_str}")
    y_b -= 10.5
    
    c.drawString(M_LEFT + 6, y_b, "PAN/IT No")
    c.drawString(M_LEFT + 75, y_b, f": {pan_str}")
    y_b -= 10.5
    
    c.drawString(M_LEFT + 6, y_b, "State Name")
    c.drawString(M_LEFT + 75, y_b, f": {state_str}")
    
    # Right Side: Terms of Delivery & Work Description Header
    y_r = Y_CUR - 11.0
    c.setFont(R, 7.5)
    c.drawString(MID_X + 6, y_r, "Terms of Delivery")
    y_r -= 10.0
    
    terms_del = str(data_dict.get("terms_of_delivery", ""))
    if terms_del:
        c.setFont(R, 8)
        c.drawString(MID_X + 6, y_r, terms_del)
        y_r -= 12.0
    else:
        y_r -= 6.0
        
    c.setFont(B, 8.5)
    work_line1 = data_dict.get("work_description", "Providing & Laying Storm Water Disposal Network in TP-241 (Chiloda) of AMC Area")
    work_line2 = data_dict.get("work_order_no", "W.O.No. 194634 dt. 12/03/2026")
    
    work_wrapped = wrap_text_to_max_width(c, work_line1, 260.0, B, 8.5)
    for w_l in work_wrapped:
        c.drawString(MID_X + 6, y_r, w_l)
        y_r -= 11.0
        
    c.drawString(MID_X + 6, y_r, work_line2)
    
    Y_CUR = BUYER_Y_BOT
    
    # -------------------------------------------------------------
    # 4. ITEMS TABLE (8 Columns matching JNP reference PDF)
    # -------------------------------------------------------------
    TABLE_HEADER_H = 22.0
    TABLE_Y_HEADER = Y_CUR - TABLE_HEADER_H
    
    col_x = [
        M_LEFT,         # 37.0 (Sl No)
        M_LEFT + 24,    # 61.0 (Description)
        M_LEFT + 183,   # 220.0 (HSN/SAC)
        M_LEFT + 238,   # 275.0 (GST Rate)
        M_LEFT + 273,   # 310.0 (Quantity)
        M_LEFT + 328,   # 365.0 (Rate)
        M_LEFT + 378,   # 415.0 (per)
        M_LEFT + 403,   # 440.0 (Amount)
        M_RIGHT         # 558.0
    ]
    
    c.rect(M_LEFT, TABLE_Y_HEADER, W, TABLE_HEADER_H)
    for x in col_x[1:-1]:
        c.line(x, TABLE_Y_HEADER, x, Y_CUR)
        
    c.setFont(B, 7.5)
    c.drawCentredString((col_x[0] + col_x[1]) / 2.0, TABLE_Y_HEADER + 12, "Sl")
    c.drawCentredString((col_x[0] + col_x[1]) / 2.0, TABLE_Y_HEADER + 3, "No.")
    
    c.drawString(col_x[1] + 12, TABLE_Y_HEADER + 7, "Description of Services")
    c.drawCentredString((col_x[2] + col_x[3]) / 2.0, TABLE_Y_HEADER + 7, "HSN/SAC")
    
    c.drawCentredString((col_x[3] + col_x[4]) / 2.0, TABLE_Y_HEADER + 12, "GST")
    c.drawCentredString((col_x[3] + col_x[4]) / 2.0, TABLE_Y_HEADER + 3, "Rate")
    
    c.drawCentredString((col_x[4] + col_x[5]) / 2.0, TABLE_Y_HEADER + 7, "Quantity")
    c.drawCentredString((col_x[5] + col_x[6]) / 2.0, TABLE_Y_HEADER + 7, "Rate")
    c.drawCentredString((col_x[6] + col_x[7]) / 2.0, TABLE_Y_HEADER + 7, "per")
    c.drawCentredString((col_x[7] + col_x[8]) / 2.0, TABLE_Y_HEADER + 7, "Amount")
    
    TABLE_BODY_H = 145.0
    TABLE_Y_BOT = TABLE_Y_HEADER - TABLE_BODY_H
    
    c.rect(M_LEFT, TABLE_Y_BOT, W, TABLE_BODY_H)
    for x in col_x[1:-1]:
        c.line(x, TABLE_Y_BOT, x, TABLE_Y_HEADER)
        
    items = data_dict.get("items", [
        {
            "sl_no": "1",
            "desc": "Contract Income Sale 18% (995424)",
            "sub_desc": "AS PER ABSTRACT OF RA BILL 1",
            "hsn": "995424",
            "gst_rate": "18 %",
            "amount": 16658209.41
        }
    ])
    
    taxable_amt = float(items[0].get("amount", 16658209.41))
    cgst_amt = round(taxable_amt * 0.09, 2)
    sgst_amt = round(taxable_amt * 0.09, 2)
    round_off = float(data_dict.get("round_off", -0.11))
    total_amt = round(taxable_amt + cgst_amt + sgst_amt + round_off, 2)
    
    y_row = TABLE_Y_HEADER - 14
    
    for itm in items:
        c.setFont(R, 8.5)
        c.drawCentredString((col_x[0] + col_x[1]) / 2.0, y_row, str(itm.get("sl_no", "1")))
        c.setFont(BI, 8)
        c.drawString(col_x[1] + 4, y_row, str(itm.get("desc", "")))
        
        c.setFont(R, 8.5)
        c.drawCentredString((col_x[2] + col_x[3]) / 2.0, y_row, str(itm.get("hsn", "")))
        c.drawCentredString((col_x[3] + col_x[4]) / 2.0, y_row, str(itm.get("gst_rate", "")))
        c.setFont(B, 8.5)
        c.drawRightString(col_x[8] - 6, y_row, format_currency(itm.get("amount", 0)))
        
        y_row -= 12
        if itm.get("sub_desc"):
            c.setFont(RI, 8)
            c.drawString(col_x[1] + 20, y_row, str(itm.get("sub_desc")))
            y_row -= 14
            
    # Tax sub-rows inside table
    c.setFont(BI, 8.5)
    c.drawString(col_x[1] + 110, y_row, "CGST")
    c.setFont(B, 8.5)
    c.drawRightString(col_x[8] - 6, y_row, format_currency(cgst_amt))
    y_row -= 12
    
    c.setFont(BI, 8.5)
    c.drawString(col_x[1] + 110, y_row, "SGST")
    c.setFont(B, 8.5)
    c.drawRightString(col_x[8] - 6, y_row, format_currency(sgst_amt))
    y_row -= 12
    
    c.setFont(RI, 8)
    c.drawString(col_x[1] + 10, y_row, "Less :")
    c.setFont(BI, 8.5)
    c.drawString(col_x[1] + 90, y_row, "Round Off")
    c.setFont(B, 8.5)
    c.drawRightString(col_x[8] - 6, y_row, format_currency(round_off))
    
    # Table Total Row
    TOTAL_ROW_H = 18.0
    TOTAL_Y_BOT = TABLE_Y_BOT - TOTAL_ROW_H
    
    c.rect(M_LEFT, TOTAL_Y_BOT, W, TOTAL_ROW_H)
    c.setFont(R, 8.5)
    c.drawRightString(col_x[7] - 10, TOTAL_Y_BOT + 5, "Total")
    c.setFont(B, 9.5)
    c.drawRightString(col_x[8] - 6, TOTAL_Y_BOT + 5, f"₹ {format_currency(total_amt)}")
    
    Y_CUR = TOTAL_Y_BOT
    
    # -------------------------------------------------------------
    # 5. AMOUNT IN WORDS
    # -------------------------------------------------------------
    WORDS_H = 18.0
    WORDS_Y_BOT = Y_CUR - WORDS_H
    
    c.rect(M_LEFT, WORDS_Y_BOT, W, WORDS_H)
    c.setFont(R, 7.5)
    c.drawString(M_LEFT + 4, WORDS_Y_BOT + 5, "Amount Chargeable (in words)")
    c.setFont(RI, 7.5)
    c.drawRightString(M_RIGHT - 4, WORDS_Y_BOT + 5, "E. & O.E")
    
    c.setFont(B, 8.5)
    amount_words = data_dict.get("amount_words", amount_to_clean_words_indian(total_amt))
    c.drawString(M_LEFT + 120, WORDS_Y_BOT + 5, amount_words)
    
    Y_CUR = WORDS_Y_BOT
    
    # -------------------------------------------------------------
    # 6. GST BREAKDOWN SUMMARY TABLE
    # -------------------------------------------------------------
    GST_GRID_H = 45.0
    GST_Y_BOT = Y_CUR - GST_GRID_H
    
    c.rect(M_LEFT, GST_Y_BOT, W, GST_GRID_H)
    
    gst_col_x = [
        M_LEFT,         # 37.0 (HSN/SAC)
        M_LEFT + 63,    # 100.0 (Taxable Value)
        M_LEFT + 153,   # 190.0 (CGST)
        M_LEFT + 243,   # 280.0 (SGST/UTGST)
        M_LEFT + 333,   # 370.0 (Total Tax)
        M_RIGHT         # 558.0
    ]
    
    for x in gst_col_x[1:-1]:
        c.line(x, GST_Y_BOT, x, Y_CUR)
        
    c.line(gst_col_x[1], Y_CUR - 14, gst_col_x[4], Y_CUR - 14)
    
    c.setFont(R, 7.5)
    c.drawCentredString((gst_col_x[0] + gst_col_x[1]) / 2.0, Y_CUR - 10, "HSN/SAC")
    c.drawCentredString((gst_col_x[1] + gst_col_x[2]) / 2.0, Y_CUR - 10, "Taxable Value")
    c.drawCentredString((gst_col_x[2] + gst_col_x[3]) / 2.0, Y_CUR - 10, "CGST")
    c.drawCentredString((gst_col_x[3] + gst_col_x[4]) / 2.0, Y_CUR - 10, "SGST/UTGST")
    c.drawCentredString((gst_col_x[4] + gst_col_x[5]) / 2.0, Y_CUR - 10, "Total Tax Amount")
    
    c.drawCentredString((gst_col_x[2] + gst_col_x[2] + 35) / 2.0, Y_CUR - 22, "Rate")
    c.drawCentredString((gst_col_x[2] + 35 + gst_col_x[3]) / 2.0, Y_CUR - 22, "Amount")
    
    c.drawCentredString((gst_col_x[3] + gst_col_x[3] + 35) / 2.0, Y_CUR - 22, "Rate")
    c.drawCentredString((gst_col_x[3] + 35 + gst_col_x[4]) / 2.0, Y_CUR - 22, "Amount")
    
    c.line(gst_col_x[2] + 30, GST_Y_BOT, gst_col_x[2] + 30, Y_CUR - 14)
    c.line(gst_col_x[3] + 30, GST_Y_BOT, gst_col_x[3] + 30, Y_CUR - 14)
    
    y_gst_row = Y_CUR - 32
    c.setFont(R, 8)
    c.drawCentredString((gst_col_x[0] + gst_col_x[1]) / 2.0, y_gst_row, "995424")
    c.drawRightString(gst_col_x[2] - 6, y_gst_row, format_currency(taxable_amt))
    
    c.drawCentredString(gst_col_x[2] + 15, y_gst_row, "9%")
    c.drawRightString(gst_col_x[3] - 6, y_gst_row, format_currency(cgst_amt))
    
    c.drawCentredString(gst_col_x[3] + 15, y_gst_row, "9%")
    c.drawRightString(gst_col_x[4] - 6, y_gst_row, format_currency(sgst_amt))
    
    total_tax_amt = cgst_amt + sgst_amt
    c.drawRightString(gst_col_x[5] - 6, y_gst_row, format_currency(total_tax_amt))
    
    c.line(M_LEFT, GST_Y_BOT + 12, M_RIGHT, GST_Y_BOT + 12)
    c.setFont(B, 7.5)
    c.drawCentredString((gst_col_x[0] + gst_col_x[1]) / 2.0, GST_Y_BOT + 3, "Total")
    c.drawRightString(gst_col_x[2] - 6, GST_Y_BOT + 3, format_currency(taxable_amt))
    c.drawRightString(gst_col_x[3] - 6, GST_Y_BOT + 3, format_currency(cgst_amt))
    c.drawRightString(gst_col_x[4] - 6, GST_Y_BOT + 3, format_currency(sgst_amt))
    c.drawRightString(gst_col_x[5] - 6, GST_Y_BOT + 3, format_currency(total_tax_amt))
    
    Y_CUR = GST_Y_BOT
    
    TAX_WORDS_H = 16.0
    TAX_WORDS_Y_BOT = Y_CUR - TAX_WORDS_H
    c.rect(M_LEFT, TAX_WORDS_Y_BOT, W, TAX_WORDS_H)
    
    c.setFont(R, 7.5)
    c.drawString(M_LEFT + 4, TAX_WORDS_Y_BOT + 4, "Tax Amount (in words)  :")
    c.setFont(B, 8.5)
    tax_words = data_dict.get("tax_words", amount_to_clean_words_indian(total_tax_amt))
    c.drawString(M_LEFT + 105, TAX_WORDS_Y_BOT + 4, tax_words)
    
    Y_CUR = TAX_WORDS_Y_BOT
    
    # -------------------------------------------------------------
    # 7. FOOTER COMPARTMENT (PAN, BANK DETAILS, DECLARATION, SIGNATURE)
    # -------------------------------------------------------------
    FOOTER_H = 130.0
    FOOTER_Y_BOT = Y_CUR - FOOTER_H
    
    c.rect(M_LEFT, FOOTER_Y_BOT, W, FOOTER_H)
    c.line(MID_X, FOOTER_Y_BOT, MID_X, Y_CUR)
    
    # Left Footer: Remarks, PAN, Declaration
    c.setFont(RI, 7.5)
    c.drawString(M_LEFT + 4, Y_CUR - 10, "Remarks:")
    c.setFont(R, 8.5)
    c.drawString(M_LEFT + 4, Y_CUR - 20, str(data_dict.get("remarks", "RA 1")))
    
    c.setFont(R, 8)
    c.drawString(M_LEFT + 4, Y_CUR - 32, "Company’s PAN")
    c.drawString(M_LEFT + 75, Y_CUR - 32, ":")
    c.setFont(B, 8.5)
    c.drawString(M_LEFT + 80, Y_CUR - 32, str(data_dict.get('seller_pan', 'AADFJ3113C')))
    
    c.setFont(R, 7.5)
    c.drawString(M_LEFT + 4, Y_CUR - 46, "Declaration")
    c.drawString(M_LEFT + 4, Y_CUR - 56, "We declare that this invoice shows the actual price of")
    c.drawString(M_LEFT + 4, Y_CUR - 65, "the goods described and that all particulars are true and")
    c.drawString(M_LEFT + 4, Y_CUR - 74, "correct.")
    
    # Right Footer: Bank Details & Authorised Signatory Box
    c.setFont(R, 7.5)
    c.drawString(MID_X + 4, Y_CUR - 10, "Company’s Bank Details")
    
    bank_info = [
        ("A/c Holder’s Name", ": JNP Infrastructure"),
        ("Bank Name", f": {data_dict.get('bank_name', 'DCB Bank Od 03342600000471')}"),
        ("A/c No.", f": {data_dict.get('account_no', '03342600000471')}"),
        ("Branch & IFS Code", f": {data_dict.get('branch_ifsc', 'Surat & DCBL0000033')}"),
        ("SWIFT Code", ": ")
    ]
    y_bk = Y_CUR - 20
    for lbl, val in bank_info:
        c.setFont(R, 7.5)
        c.drawString(MID_X + 4, y_bk, lbl)
        if "Holder" in lbl or "Name" in lbl or "No" in lbl or "IFS" in lbl:
            c.setFont(B, 8)
        else:
            c.setFont(R, 8)
        c.drawString(MID_X + 80, y_bk, val)
        y_bk -= 10.0
        
    c.setFont(B, 8)
    c.drawRightString(M_RIGHT - 8, Y_CUR - 75, "for JNP Infrastructure (GJ)")
    c.setFont(R, 7)
    c.drawRightString(M_RIGHT - 8, FOOTER_Y_BOT + 8, "Authorised Signatory")
    
    Y_CUR = FOOTER_Y_BOT
    
    # -------------------------------------------------------------
    # 8. BOTTOM LEGAL NOTICES
    # -------------------------------------------------------------
    c.setFont(R, 8.5)
    c.drawCentredString(PAGE_W / 2.0, Y_CUR - 12, "SUBJECT TO SURAT JURISDICTION")
    c.drawCentredString(PAGE_W / 2.0, Y_CUR - 24, "This is a Computer Generated Invoice")
    
    c.save()
    print(f"[SUCCESS] Fixed Non-Overlapping JNP Invoice generated at: {output_pdf_path}")
    return output_pdf_path
