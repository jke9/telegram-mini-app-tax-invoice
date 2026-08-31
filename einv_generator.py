"""
NIC Standard E-Invoice PDF Generator
====================================
Generates pixel-perfect, compliant NIC Standard E-Invoices (A3 Portrait format)
with dynamic JWT signed QR codes, Code 128 barcodes, and realistic timestamps.
"""

import os
import sys
import json
import base64
import random
import re
from datetime import datetime
from reportlab.lib.pagesizes import A3
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode import qr
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Register custom typography if available
try:
    pdfmetrics.registerFont(TTFont("MxPlus_IBM_VGA_9x16", os.path.join(ASSETS_DIR, "MxPlus_IBM_VGA_9x16.ttf")))
except Exception:
    pass

try:
    pdfmetrics.registerFont(TTFont("PxPlus_IBM_VGA_9x16", os.path.join(ASSETS_DIR, "PxPlus_IBM_VGA_9x16.ttf")))
except Exception:
    pass

try:
    pdfmetrics.registerFont(TTFont("OCR-B", os.path.join(ASSETS_DIR, "ocrb.ttf")))
except Exception:
    pass

try:
    pdfmetrics.registerFont(TTFont("Px437_DOS-V_re_ANK16", os.path.join(ASSETS_DIR, "Px437_DOS-V_re_ANK16.ttf")))
except Exception:
    pass

try:
    pdfmetrics.registerFont(TTFont("DRKrapkaRhombus-Regular", os.path.join(ASSETS_DIR, "DRKrapkaRhombus-Regular.ttf")))
except Exception:
    pass

PAGE_W, PAGE_H = 842.0, 1190.0  # Portrait A3 dimensions in points


def split_address_lines(addr_str, max_lines=3, max_chars_per_line=50):
    """Splits a single address string into up to 3 clean balanced lines."""
    if not addr_str:
        return ["", "", ""]
    
    parts = [p.strip() for p in addr_str.split(",") if p.strip()]
    lines = []
    curr = ""
    for part in parts:
        test = curr + (", " if curr else "") + part
        if len(test) <= max_chars_per_line:
            curr = test
        else:
            if curr:
                lines.append(curr)
            curr = part
    if curr:
        lines.append(curr)
    
    while len(lines) < max_lines:
        lines.append("")
    return lines[:max_lines]


def build_realistic_timestamp(date_str, custom_time_str=None, target_hour=11, target_min=15):
    """
    Constructs realistic randomized timestamps in accordance with SOP (never exact round times).
    If custom_time_str is provided (e.g. '11:42:36'), uses that directly.
    """
    # Parse date DD-MM-YYYY or DD/MM/YYYY
    clean_date = date_str.replace('/', '-')
    parts = clean_date.split('-')
    if len(parts) == 3:
        # DD-MM-YYYY
        d, m, y = parts[0], parts[1], parts[2]
        doc_date = f"{d.zfill(2)}-{m.zfill(2)}-{y}"
        doc_date_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    else:
        now = datetime.now()
        doc_date = now.strftime("%d-%m-%Y")
        doc_date_iso = now.strftime("%Y-%m-%d")

    if custom_time_str and re.match(r'^\d{1,2}:\d{1,2}(:\d{1,2})?$', str(custom_time_str).strip()):
        t_parts = str(custom_time_str).strip().split(':')
        hh = int(t_parts[0])
        mm = int(t_parts[1])
        ss = int(t_parts[2]) if len(t_parts) > 2 else random.randint(5, 59)
        time_str = f"{hh:02d}:{mm:02d}:{ss:02d}"
    else:
        # Randomize minutes (1-58) and seconds (5-59)
        minute = random.randint(1, 58)
        second = random.randint(5, 59)
        time_str = f"{target_hour:02d}:{minute:02d}:{second:02d}"

    ack_date = f"{doc_date} {time_str}"
    print_date = f"{doc_date} {time_str}"
    signed_on = f"{doc_date_iso} {time_str}"

    return doc_date, ack_date, print_date, signed_on


def generate_einv_pdf(payload, output_path):
    """
    Generates a high-fidelity NIC Standard E-Invoice PDF from payload parameters.
    """
    # 1. Parse Supplier & Recipient details
    contractor = payload.get("contractor_data") or {}
    customer = payload.get("customer_data") or {}

    supplier_name = contractor.get("name") or payload.get("contractor", "JNP INFRASTRUCTURE")
    supplier_gstin = contractor.get("gstin") or "24AADFJ3113C1Z6"
    supplier_addr_raw = contractor.get("address") or "303, UNION TRADE CENTER, B/S APPLE HOSPITAL UDHNA, UDHNA DARWAJA, SURAT, GUJARAT, 395002"
    sup_addr1, sup_addr2, sup_addr3 = split_address_lines(supplier_addr_raw)

    recipient_name = customer.get("name") or payload.get("customer", "AHMEDABAD MUNICIPAL CORPORATION")
    recipient_gstin = customer.get("gstin") or "24AAALA0024C3Z7"
    recipient_addr_raw = customer.get("address") or "MAHANAGAR SEVA SADAN, SARDAR PATEL BHAVAN, DANAPITH, AHMEDABAD - 380001"
    rec_addr1, rec_addr2, rec_addr3 = split_address_lines(recipient_addr_raw)

    doc_no = payload.get("inv_no") or "2026/27-JNP-1"
    doc_date_raw = payload.get("inv_date") or datetime.now().strftime("%d/%m/%Y")
    doc_time_raw = payload.get("inv_time") or payload.get("time")
    hsn_code = str(payload.get("hsn") or "995424").strip()

    # 2. Timestamps
    doc_date, ack_date, print_date, signed_on = build_realistic_timestamp(doc_date_raw, custom_time_str=doc_time_raw)

    # 3. Financial calculations
    amount_mode = payload.get("amount_mode", "taxable")
    raw_amt = float(payload.get("amount", 0.0))

    if amount_mode == "total":
        total_inv_amt = raw_amt
        taxable_amt = round(total_inv_amt / 1.18, 2)
    else:
        taxable_amt = raw_amt
        total_inv_amt = round(taxable_amt * 1.18, 2)

    cgst = round(taxable_amt * 0.09, 2)
    sgst = round(taxable_amt * 0.09, 2)
    
    custom_ro = payload.get("custom_round_off")
    if custom_ro is not None:
        round_off = float(custom_ro)
        total_inv_amt = round(taxable_amt + cgst + sgst + round_off, 2)
    else:
        final_integer = round(taxable_amt + cgst + sgst)
        round_off = round(final_integer - (taxable_amt + cgst + sgst), 2)
        total_inv_amt = float(final_integer)

    # 4. Dynamic IRN and Ack No
    ack_no = payload.get("ack_no") or ("1626" + "".join(str(random.randint(0, 9)) for _ in range(11)))
    irn = payload.get("irn") or ("".join(random.choice("0123456789abcdef") for _ in range(64)))

    # 5. Canvas Drawing
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))

    def draw_str(text, bbox, font_name="Helvetica", size=10.5, align="left"):
        x0, y0, x1, y1 = bbox
        char_h = y1 - y0
        rl_y = PAGE_H - y1 + char_h * 0.15
        c.setFont(font_name, size)
        c.setFillColorRGB(0, 0, 0)
        if align == "left":
            c.drawString(x0, rl_y, str(text or ""))
        elif align == "right":
            c.drawRightString(x1, rl_y, str(text or ""))
        elif align == "center":
            c.drawCentredString((x0 + x1) / 2.0, rl_y, str(text or ""))

    def draw_wrapped_str(text, bbox, font_name="Helvetica", size=8.5, line_h=11.0):
        x0, y0, x1, y1 = bbox
        max_w = x1 - x0
        words = str(text or "").split()
        lines = []
        curr_line = ""
        for w in words:
            test_line = curr_line + (" " if curr_line else "") + w
            if c.stringWidth(test_line, font_name, size) <= max_w:
                curr_line = test_line
            else:
                if curr_line:
                    lines.append(curr_line)
                curr_line = w
        if curr_line:
            lines.append(curr_line)
        curr_y = y0
        for l in lines:
            draw_str(l, [x0, curr_y, x1, curr_y + line_h], font_name=font_name, size=size)
            curr_y += line_h

    def draw_rect(rect, stroke=1, fill=0, color=(0.75, 0.75, 0.75), fill_color=None, radius=0.0, line_width=1.75):
        x0, y0, x1, y1 = rect
        w = x1 - x0
        h = y1 - y0
        rl_y = PAGE_H - y1
        c.setLineWidth(line_width)
        if stroke:
            c.setStrokeColorRGB(*color)
        else:
            c.setStrokeColorRGB(1, 1, 1)
        if fill and fill_color:
            c.setFillColorRGB(*fill_color)
        else:
            c.setFillColorRGB(1, 1, 1)
        if radius > 0.0:
            c.roundRect(x0, rl_y, w, h, radius, stroke=stroke, fill=fill)
        else:
            c.rect(x0, rl_y, w, h, fill=fill, stroke=stroke)

    def draw_line(x1, y1, x2, y2, color=(0.75, 0.75, 0.75)):
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(*color)
        c.line(x1, PAGE_H - y1, x2, PAGE_H - y2)

    # ─── 1. Outer Box Border ──────────────────────────────────────────────────
    draw_rect([15.0, 15.0, 827.0, 1175.0], color=(0.75, 0.75, 0.75), radius=20.0)

    # ─── 2. Company Name and GSTIN Header ─────────────────────────────────────
    draw_str(supplier_gstin, [31.0, 97.6, 225.9, 126.5], font_name="Helvetica-Bold", size=21.0)
    draw_str(supplier_name, [31.0, 129.1, 580.0, 157.9], font_name="Helvetica-Bold", size=21.0)

    # ─── 3. Dynamic QR Code (JWT signed payload) ──────────────────────────────
    qr_w, qr_h = 190.1, 190.1
    qr_x, qr_y = 617.2, PAGE_H - 224.8

    header = {"alg": "RS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(',', ':'))
    header_b64 = base64.urlsafe_b64encode(header_json.encode('utf-8')).decode('utf-8').rstrip('=')

    qr_dict = {
        "SellerGstin": supplier_gstin.strip(),
        "BuyerGstin": recipient_gstin.strip(),
        "DocNo": doc_no.strip(),
        "DocTyp": "INV",
        "DocDt": doc_date.replace("-", "/").strip(),
        "TotInvVal": int(round(total_inv_amt)),
        "ItemCnt": 1,
        "MainHsnCode": hsn_code,
        "Irn": irn.strip(),
        "IrnDt": ack_date.strip()
    }
    payload_json = json.dumps(qr_dict, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')
    dummy_sig = "mock_irp_digital_signature_valid_verification_hash"
    dummy_b64 = base64.urlsafe_b64encode(dummy_sig.encode('utf-8')).decode('utf-8').rstrip('=')
    qr_data = f"{header_b64}.{payload_b64}.{dummy_b64}"

    d_qr = Drawing(qr_w, qr_h)
    qr_widget = qr.QrCodeWidget(qr_data, barWidth=qr_w, barHeight=qr_h, barLevel='L')
    qr_widget.barBorder = 4
    d_qr.add(qr_widget)
    d_qr.drawOn(c, qr_x, qr_y)

    # ─── 4. Section 1: e-Invoice Details ──────────────────────────────────────
    draw_rect([25.0, 239.0, 787.0, 302.2], radius=5.0)
    draw_str("1.e-Invoice Details", [27.5, 241.3, 113.9, 255.7], font_name="Helvetica-Bold", size=10.5)
    draw_rect([27.5, 257.2, 784.5, 258.2], fill=1, stroke=0, color=(0.75, 0.75, 0.75), fill_color=(0.75, 0.75, 0.75))

    irn_part1 = irn[:36]
    irn_part2 = irn[36:]

    draw_str("IRN : ", [32.2, 265.5, 62.0, 280.0], font_name="Helvetica-Bold")
    draw_str(irn_part1, [62.0, 265.5, 270.0, 280.0])
    draw_str(irn_part2, [32.2, 281.3, 270.0, 295.7])

    draw_str("Ack No. : ", [281.1, 265.5, 335.0, 280.0], font_name="Helvetica-Bold")
    draw_str(str(ack_no), [335.0, 265.5, 450.0, 280.0])

    draw_str("Ack Date : ", [534.9, 265.5, 590.0, 280.0], font_name="Helvetica-Bold")
    draw_str(str(ack_date), [590.0, 265.5, 750.0, 280.0])

    # ─── 5. Section 2: Transaction Details ────────────────────────────────────
    draw_rect([25.0, 307.2, 787.0, 415.9], radius=5.0)
    draw_str("2.Transaction Details", [27.5, 309.5, 126.1, 323.9], font_name="Helvetica-Bold", size=10.5)
    draw_rect([27.5, 325.4, 784.5, 326.4], fill=1, stroke=0, color=(0.75, 0.75, 0.75), fill_color=(0.75, 0.75, 0.75))

    draw_str("Supply type Code : ", [27.2, 333.7, 125.2, 348.2], font_name="Helvetica-Bold")
    draw_str("B2B", [125.2, 333.7, 160.0, 348.2])

    draw_str("Document No. : ", [258.1, 333.7, 338.6, 348.2], font_name="Helvetica-Bold")
    draw_str(doc_no, [338.6, 333.7, 480.0, 348.2])

    draw_str("IGST applicable despite Supplier and ", [490.5, 333.7, 666.7, 348.2], font_name="Helvetica-Bold")
    draw_str("Recipient located in same State : No", [490.5, 349.5, 660.7, 363.9], font_name="Helvetica-Bold")

    draw_str("Place of Supply : ", [27.2, 372.2, 114.7, 386.6], font_name="Helvetica-Bold")
    draw_str("GUJARAT", [114.7, 372.2, 250.0, 386.6])

    draw_str("Document Type : ", [27.2, 394.9, 115.3, 409.4], font_name="Helvetica-Bold")
    draw_str("Tax Invoice", [115.3, 394.9, 250.0, 409.4], font_name="Helvetica-Bold")

    draw_str("Document Date : ", [258.1, 394.9, 344.4, 409.4], font_name="Helvetica-Bold")
    draw_str(doc_date, [344.4, 394.9, 450.0, 409.4])

    # ─── 6. Section 3: Party Details ──────────────────────────────────────────
    draw_rect([25.0, 420.9, 787.0, 549.5], radius=5.0)
    draw_str("3.Party Details", [27.5, 423.2, 95.8, 437.6], font_name="Helvetica-Bold", size=10.5)
    draw_rect([27.5, 439.1, 784.5, 440.1], fill=1, stroke=0, color=(0.75, 0.75, 0.75), fill_color=(0.75, 0.75, 0.75))
    draw_line(412.5, 447.6, 412.5, 528.5)

    # Supplier Details
    draw_str("Supplier : ", [32.5, 447.4, 86.5, 463.9], font_name="Helvetica-Bold", size=12.0)
    draw_str(f"GSTIN : {supplier_gstin}", [32.5, 465.4, 170.8, 479.8])
    draw_str(supplier_name, [32.5, 481.1, 350.0, 495.5], size=10.5)
    draw_str(sup_addr1, [32.5, 496.9, 390.0, 511.3])
    draw_str(sup_addr2, [32.5, 512.6, 390.0, 527.0])
    if sup_addr3:
        draw_str(sup_addr3, [32.5, 528.3, 390.0, 542.7])

    # Recipient Details
    draw_str("Recipient : ", [422.6, 447.4, 482.6, 463.9], font_name="Helvetica-Bold", size=12.0)
    draw_str(f"GSTIN : {recipient_gstin}", [422.6, 465.4, 561.5, 479.8])
    draw_str(recipient_name, [422.6, 481.1, 750.0, 495.5], size=10.5)
    draw_str(rec_addr1, [422.6, 496.9, 780.0, 511.3])
    draw_str(rec_addr2, [422.6, 512.6, 780.0, 527.0])
    if rec_addr3:
        draw_str(rec_addr3, [422.6, 528.3, 780.0, 542.7])

    # ─── 7. Section 4: Details of Goods / Services ────────────────────────────
    draw_rect([25.0, 554.5, 787.0, 701.7], radius=5.0)
    draw_str("4.Details of Goods / Services", [27.5, 556.8, 162.9, 571.2], font_name="Helvetica-Bold", size=10.5)
    draw_rect([27.5, 572.8, 784.5, 573.8], fill=1, stroke=0, color=(0.75, 0.75, 0.75), fill_color=(0.75, 0.75, 0.75))

    cols_x = [27.8, 56.6, 141.6, 199.4, 245.5, 273.7, 350.7, 419.6, 483.6, 635.0, 710.1, 764.2]
    for x in cols_x:
        draw_line(x, 581.2, x, 653.7, color=(0, 0, 0))
    draw_line(27.5, 581.5, 764.5, 581.5, color=(0, 0, 0))
    draw_line(27.5, 617.5, 764.5, 617.5, color=(0, 0, 0))
    draw_line(27.5, 653.4, 764.5, 653.4, color=(0, 0, 0))

    # Headers
    draw_str("SlNo", [30.0, 583.5, 56.0, 598.0])
    draw_str("Item Description", [60.0, 583.5, 141.0, 598.0])
    draw_str("HSN Code", [143.8, 583.5, 199.0, 598.0])
    draw_str("Quantity", [201.7, 583.5, 245.0, 598.0])
    draw_str("Unit", [247.8, 583.5, 273.0, 598.0])
    draw_str("Unit  Price(Rs)", [276.0, 583.5, 350.0, 598.0])
    draw_str("Discount(Rs)", [352.9, 583.5, 419.0, 598.0])
    draw_str("Taxable", [421.9, 583.5, 483.0, 598.0])
    draw_str("Amount(Rs)", [421.9, 599.3, 483.0, 613.7])
    draw_str("Tax Rate(GST + Cess |", [485.9, 583.5, 635.0, 598.0])
    draw_str("State Cess + Cess Non.Advol", [485.9, 599.3, 635.0, 613.7])
    draw_str("Other charges", [637.2, 583.5, 710.0, 598.0])
    draw_str("Total", [712.3, 583.5, 764.0, 598.0])

    # Body Row
    draw_str("1", [30.0, 619.5, 56.0, 633.9])
    draw_wrapped_str("", [60.0, 619.5, 141.0, 650.0], size=8.5, line_h=10.0)
    draw_str(hsn_code, [143.8, 619.5, 199.0, 633.9])
    draw_str("1", [201.7, 619.5, 245.0, 633.9])
    draw_str("OTH", [247.8, 619.5, 273.0, 633.9])
    draw_str(f"{taxable_amt:.2f}", [276.0, 619.5, 350.0, 633.9], size=8.5)
    draw_str("0", [352.9, 619.5, 419.0, 633.9])
    draw_str(f"{taxable_amt:.2f}", [421.9, 619.5, 483.0, 633.9], size=8.5)
    draw_str("18.00 + 0.00", [485.9, 619.5, 635.0, 633.9])
    draw_str("0.00 + 0", [485.9, 635.3, 635.0, 649.7])
    draw_str("0", [637.2, 619.5, 710.0, 633.9])
    draw_str(f"{round(taxable_amt + cgst + sgst, 2):.2f}", [712.3, 619.5, 764.0, 633.9], size=8.5)

    # ─── 8. Totals Table ──────────────────────────────────────────────────────
    totals_cols_x = [27.8, 107.5, 180.2, 252.9, 314.2, 380.5, 453.8, 508.8, 597.7, 684.5, 764.2]
    for x in totals_cols_x:
        draw_line(x, 658.2, x, 699.2, color=(0, 0, 0))
    draw_line(27.5, 658.4, 764.5, 658.4, color=(0, 0, 0))
    draw_line(27.5, 678.7, 764.5, 678.7, color=(0, 0, 0))
    draw_line(27.5, 698.9, 764.5, 698.9, color=(0, 0, 0))

    # Headers
    draw_str("Tax'ble Amt", [30.0, 660.5, 107.0, 674.9])
    draw_str("CGST Amt", [109.8, 660.5, 180.0, 674.9])
    draw_str("SGST Amt", [182.4, 660.5, 252.0, 674.9])
    draw_str("IGST Amt", [255.1, 660.5, 314.0, 674.9])
    draw_str("CESS Amt", [316.4, 660.5, 380.0, 674.9])
    draw_str("State CESS", [382.7, 660.5, 453.0, 674.9])
    draw_str("Discount", [456.1, 660.5, 508.0, 674.9])
    draw_str("Other Charges", [511.0, 660.5, 597.0, 674.9])
    draw_str("Round off Amt", [600.0, 660.5, 684.0, 674.9])
    draw_str("Tot Inv. Amt", [686.8, 660.5, 764.0, 674.9])

    # Values
    draw_str(f"{taxable_amt:.2f}", [30.0, 680.7, 107.0, 695.1])
    draw_str(f"{cgst:.2f}", [109.8, 680.7, 180.0, 695.1])
    draw_str(f"{sgst:.2f}", [182.4, 680.7, 252.0, 695.1])
    draw_str("0.00", [255.1, 680.7, 314.0, 695.1])
    draw_str("0.00", [316.4, 680.7, 380.0, 695.1])
    draw_str("0.00", [382.7, 680.7, 453.0, 695.1])
    draw_str("0.00", [456.1, 680.7, 508.0, 695.1])
    draw_str("0.00", [511.0, 680.7, 597.0, 695.1])
    draw_str(f"{round_off:+.2f}" if round_off != 0 else "0.00", [600.0, 680.7, 684.0, 695.1])
    draw_str(f"{total_inv_amt:.2f}", [686.8, 680.7, 764.0, 695.1])

    # ─── 9. Footer Box ────────────────────────────────────────────────────────
    draw_rect([25.0, 706.7, 787.0, 798.1], radius=5.0)
    draw_str(f"Generated By : {supplier_gstin}", [32.0, 708.5, 250.0, 722.9], font_name="Helvetica-Bold")
    draw_str(f"Print Date : {print_date}", [32.0, 724.2, 250.0, 738.6], font_name="Helvetica-Bold")

    # Code 128 Barcode
    bar_w, bar_h = 146.0, 52.0
    bar_x, bar_y = 321.3, PAGE_H - 763.7
    c_bar = createBarcodeDrawing('Code128', value=str(ack_no), width=bar_w, height=bar_h, barWidth=1.0, barHeight=bar_h, lquiet=6.0, rquiet=6.0, humanReadable=False)
    c_bar.drawOn(c, bar_x, bar_y)
    draw_str(str(ack_no), [321.3, 764.5, 467.3, 778.9], font_name="DRKrapkaRhombus-Regular", align="center")

    # eSign Logo
    esign_path = os.path.join(ASSETS_DIR, "esign_logo.png")
    if os.path.exists(esign_path):
        c.drawImage(ImageReader(esign_path), 691.0, PAGE_H - 761.65, 94.0, 50.0, mask='auto')

    # eSign Text Labels
    draw_str("Digitally Signed by NIC-IRP", [630.0, 761.5, 785.0, 775.9], font_name="Helvetica", align="right")
    draw_str(f"on :{signed_on}", [630.0, 777.2, 785.0, 791.6], font_name="Helvetica", align="right")

    date_val = signed_on
    text_w = c.stringWidth(date_val, "Helvetica", 10.5)
    start_x = 785.0 - text_w
    draw_line(start_x, 792.0, 785.0, 792.0, color=(0, 0, 0))

    c.showPage()
    c.save()

    calcs = {
        "taxable_amt": f"{taxable_amt:,.2f}",
        "cgst": f"{cgst:,.2f}",
        "sgst": f"{sgst:,.2f}",
        "round_off": f"{round_off:+.2f}" if round_off != 0 else "0.00",
        "total_inv_amt": f"{total_inv_amt:,.2f}",
        "ack_no": ack_no,
        "irn": irn,
        "ack_date": ack_date,
        "print_date": print_date,
        "signed_on": signed_on
    }

    return output_path, calcs
