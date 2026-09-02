# -*- coding: utf-8 -*-
"""
MOP (Memorandum of Payment) Generator & Vector PDF Engine
Matches the exact layout, formulas, and visual fidelity from 'Tax Invoice Formate Updates.xlsm' (MOP sheet).
"""
import os
import sys
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─── Helper: Indian Currency Number Formatting ────────────────────────────────
def fmt_indian(val):
    try:
        fval = abs(float(val))
        is_neg = float(val) < 0
        s = f"{fval:.2f}"
        int_part, dec_part = s.split(".")
        if len(int_part) <= 3:
            res = int_part
        else:
            last3 = int_part[-3:]
            rest = int_part[:-3]
            groups = []
            while len(rest) > 2:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.insert(0, rest)
            res = ",".join(groups) + "," + last3
        formatted = f"{res}.{dec_part}"
        return f"-{formatted}" if is_neg else formatted
    except Exception:
        return str(val)


# ─── Helper: Number to Indian Currency Words ──────────────────────────────────
ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digits_to_words(n):
    if n == 0:
        return ""
    if n < 20:
        return ONES[n]
    tens_digit = n // 10
    ones_digit = n % 10
    return TENS[tens_digit] + (" " + ONES[ones_digit] if ones_digit != 0 else "")


def _three_digits_to_words(n):
    hundred = n // 100
    rem = n % 100
    res = ""
    if hundred > 0:
        res += ONES[hundred] + " Hundred"
    if rem > 0:
        if res:
            res += " "
        res += _two_digits_to_words(rem)
    return res


def num_to_words_indian(num):
    """Converts a number to Indian currency words format (Crore, Lakh, Thousand, Hundred)."""
    try:
        n = int(round(float(num)))
    except Exception:
        return ""

    if n == 0:
        return "Zero Rupees Only"

    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    rem = n

    parts = []
    if crore > 0:
        parts.append(_two_digits_to_words(crore) + " Crore")
    if lakh > 0:
        parts.append(_two_digits_to_words(lakh) + " Lakh")
    if thousand > 0:
        parts.append(_two_digits_to_words(thousand) + " Thousand")
    if rem > 0:
        parts.append(_three_digits_to_words(rem))

    words = " ".join(p for p in parts if p).strip()
    return f"{words} Rupees Only"


# ─── Calculation Engine ───────────────────────────────────────────────────────
def calculate_mop(gross_amount, config=None, custom_round_off=None):
    """
    Computes all intermediate values, statutory deductions, tax breakdowns,
    and net payable for Memorandum of Payment (MOP).
    """
    cfg = config or {}
    G = float(gross_amount or 0.0)

    # Percentage Parameters
    agency_tds_pct = float(cfg.get("agency_tds_pct", 2.0))
    agency_sgst_tds_pct = float(cfg.get("agency_sgst_tds_pct", 1.0))
    agency_cgst_tds_pct = float(cfg.get("agency_cgst_tds_pct", 1.0))
    admin_expense_pct = float(cfg.get("admin_expense_pct", 3.25))
    it_tds_pct = float(cfg.get("it_tds_pct", 1.0))
    retention_pct = float(cfg.get("retention_pct", 2.0))
    labour_cess_pct = float(cfg.get("labour_cess_pct", 1.0))
    testing_fee_pct = float(cfg.get("testing_fee_pct", 0.5))

    # Basic Work Done = G / 1.18
    b_work = G / 1.18 if G > 0 else 0.0

    # Section B: Agency Deductions
    agency_tds = b_work * (agency_tds_pct / 100.0)
    agency_sgst = b_work * (agency_sgst_tds_pct / 100.0)
    agency_cgst = b_work * (agency_cgst_tds_pct / 100.0)
    agency_deductions_total = agency_tds + agency_sgst + agency_cgst

    # Section (A - B)
    net_work_done = G - agency_deductions_total

    # Admin & Head Expense
    admin_expense = G * (admin_expense_pct / 100.0)

    # Our Bill Amount
    our_bill_gross = net_work_done - admin_expense
    our_basic = (our_bill_gross / 1.18) if our_bill_gross > 0 else 0.0
    our_sgst = our_basic * 0.09
    our_cgst = our_basic * 0.09

    # Our Deductions
    it_tds = our_basic * (it_tds_pct / 100.0)
    retention = G * (retention_pct / 100.0)
    labour_cess = b_work * (labour_cess_pct / 100.0)
    testing_fee = G * (testing_fee_pct / 100.0)

    # Raw Net and Round Off
    raw_net = our_bill_gross - it_tds - retention - labour_cess - testing_fee
    if custom_round_off is not None:
        try:
            round_off = float(custom_round_off)
            net_payable_rounded = round(raw_net + round_off, 2)
        except Exception:
            net_payable_rounded = float(round(raw_net))
            round_off = net_payable_rounded - raw_net
    else:
        net_payable_rounded = float(round(raw_net))
        round_off = net_payable_rounded - raw_net

    return {
        # Raw numerical floats
        "gross_amount": G,
        "basic_work": b_work,
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
        "round_off": round_off,
        "net_payable": net_payable_rounded,
        # Percentage metadata
        "pct_config": {
            "agency_tds_pct": agency_tds_pct,
            "agency_sgst_tds_pct": agency_sgst_tds_pct,
            "agency_cgst_tds_pct": agency_cgst_tds_pct,
            "admin_expense_pct": admin_expense_pct,
            "it_tds_pct": it_tds_pct,
            "retention_pct": retention_pct,
            "labour_cess_pct": labour_cess_pct,
            "testing_fee_pct": testing_fee_pct,
        },
        # Formatted Indian currency strings
        "str_gross_amount": fmt_indian(G),
        "str_basic_work": fmt_indian(b_work),
        "str_agency_tds": fmt_indian(agency_tds),
        "str_agency_sgst": fmt_indian(agency_sgst),
        "str_agency_cgst": fmt_indian(agency_cgst),
        "str_agency_deductions_total": fmt_indian(agency_deductions_total),
        "str_net_work_done": fmt_indian(net_work_done),
        "str_admin_expense": fmt_indian(admin_expense),
        "str_our_bill_gross": fmt_indian(our_bill_gross),
        "str_our_basic": fmt_indian(our_basic),
        "str_our_sgst": fmt_indian(our_sgst),
        "str_our_cgst": fmt_indian(our_cgst),
        "str_it_tds": fmt_indian(it_tds),
        "str_retention": fmt_indian(retention),
        "str_labour_cess": fmt_indian(labour_cess),
        "str_testing_fee": fmt_indian(testing_fee),
        "str_round_off": f"{round_off:+.2f}" if round_off != 0 else "0.00",
        "str_net_payable": fmt_indian(net_payable_rounded),
        "amount_in_words": num_to_words_indian(net_payable_rounded)
    }


# ─── ReportLab Vector PDF Generator ──────────────────────────────────────────
def draw_mop_pdf(mop_data, output_pdf):
    """
    Renders clean, high-precision ReportLab vector PDF for Memorandum of Payment.
    """
    c = canvas.Canvas(output_pdf, pagesize=A4)
    PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt

    # Margins
    M_L = 36.0
    M_R = PAGE_W - 36.0
    M_T = PAGE_H - 36.0
    M_B = 36.0
    BOX_W = M_R - M_L

    # Fonts
    R = "Helvetica"
    B = "Helvetica-Bold"

    # Outer border
    c.setLineWidth(1.0)
    c.setStrokeColor(colors.black)
    c.rect(M_L, M_B, BOX_W, M_T - M_B)

    # ── Header ───────────────────────────────────────────────────────────────
    contractor = mop_data.get("contractor_name", "Jay Khodiyar Enterprise")
    contractor_gstin = mop_data.get("contractor_gstin", "24BJHPP5061K1ZZ")
    agency_name = mop_data.get("agency_name", "JNP INFRASTRUCTURE")
    agency_gstin = mop_data.get("agency_gstin", "24AADFJ3113C1Z6")
    work_name = mop_data.get("work_name", mop_data.get("project_description", "Providing & Laying Sewerage Network"))
    bill_sr_no = mop_data.get("bill_sr_no", "15/26-27")
    date_of_record = mop_data.get("date_of_record", datetime.date.today().strftime("%d/%m/%Y"))
    ra_bill_no = mop_data.get("ra_bill_no", "RA BILL NO. 01")
    ra_bill_date = mop_data.get("ra_bill_date", datetime.date.today().strftime("%d/%m/%Y"))

    # Top Company Name
    curr_y = M_T - 22.0
    c.setFont(B, 13)
    c.drawCentredString(PAGE_W / 2.0, curr_y, contractor)

    # Subtitle
    curr_y -= 14.0
    c.setFont(B, 10.5)
    c.drawCentredString(PAGE_W / 2.0, curr_y, "MEMORANDUM OF PAYMENT")

    # Dividing Header Line
    curr_y -= 8.0
    c.setLineWidth(0.6)
    c.line(M_L, curr_y, M_R, curr_y)

    # ── Metadata Block ────────────────────────────────────────────────────────
    c.setFont(R, 8.5)
    row_h = 13.0

    # Row 1: Name of Agency + GST
    curr_y -= row_h
    c.drawString(M_L + 8, curr_y, "Name of Agency")
    c.drawString(M_L + 95, curr_y, f":  {agency_name}")
    c.drawString(M_L + 340, curr_y, "GST NO. :")
    c.drawString(M_L + 395, curr_y, agency_gstin)

    # Row 2: Name of Work (auto truncate / fit)
    curr_y -= row_h
    c.drawString(M_L + 8, curr_y, "Name of Work")
    w_text = f":  {work_name}"
    if c.stringWidth(w_text, R, 8.5) > (BOX_W - 110):
        # Truncate nicely
        while c.stringWidth(w_text + "...", R, 8.5) > (BOX_W - 110) and len(w_text) > 10:
            w_text = w_text[:-1]
        w_text += "..."
    c.drawString(M_L + 95, curr_y, w_text)

    # Row 3: Sr. No. of the Bill
    curr_y -= row_h
    c.drawString(M_L + 8, curr_y, "Sr. No. of the Bill")
    c.drawString(M_L + 95, curr_y, f":  {bill_sr_no}")

    # Row 4: Date of Record
    curr_y -= row_h
    c.drawString(M_L + 8, curr_y, "Date of Record")
    c.drawString(M_L + 95, curr_y, f":  {date_of_record}")

    # Row 5: RA Bill No. + Date + Contractor GSTIN
    curr_y -= row_h
    c.setFont(B, 8.5)
    c.drawString(M_L + 8, curr_y, ra_bill_no)
    c.drawString(M_L + 210, curr_y, f"DATE : {ra_bill_date}")
    c.drawString(M_L + 340, curr_y, f"GST NO.: {contractor_gstin}")

    # Dividing Line
    curr_y -= 6.0
    c.setLineWidth(0.6)
    c.line(M_L, curr_y, M_R, curr_y)

    # ── Title: Memorandum of Payment ──────────────────────────────────────────
    curr_y -= 16.0
    c.setFont(B, 11)
    title = "Memorandum of Payment"
    c.drawCentredString(PAGE_W / 2.0, curr_y, title)
    t_w = c.stringWidth(title, B, 11)
    c.setLineWidth(0.7)
    c.line((PAGE_W / 2.0) - (t_w / 2.0), curr_y - 2, (PAGE_W / 2.0) + (t_w / 2.0), curr_y - 2)

    # Line before calculation table
    curr_y -= 10.0
    c.setLineWidth(0.6)
    c.line(M_L, curr_y, M_R, curr_y)

    # ── Financial Calculation Breakdown ───────────────────────────────────────
    calcs = mop_data.get("calculations") or calculate_mop(mop_data.get("amount", 0), mop_data.get("config"))
    pcts = calcs["pct_config"]

    # Table coordinates
    COL_DESC_X = M_L + 12
    COL_COLON_X = M_L + 330
    COL_RS_X = M_L + 360
    COL_VAL_R = M_R - 15

    line_gap = 14.5

    def draw_calc_row(desc, val_str, bold=False, indent=0, show_rs=True, colon=True):
        nonlocal curr_y
        curr_y -= line_gap
        c.setFont(B if bold else R, 8.5)
        c.drawString(COL_DESC_X + indent, curr_y, desc)
        if colon:
            c.drawString(COL_COLON_X, curr_y, ":")
        if show_rs and val_str:
            c.drawString(COL_RS_X, curr_y, "Rs.")
        if val_str:
            c.drawRightString(COL_VAL_R, curr_y, str(val_str))

    # Section (A)
    draw_calc_row("  (A)", "", bold=True, colon=False)
    draw_calc_row("  Total work done amount as per R A Bill", calcs["str_gross_amount"], bold=True)

    # Section (B)
    curr_y -= 4
    draw_calc_row("  (B)", "", bold=True, colon=False)
    draw_calc_row("  Less Amount", "", bold=True, colon=True, show_rs=False)
    draw_calc_row(f"  Less : TDS {pcts['agency_tds_pct']:.0f}%", calcs["str_agency_tds"], indent=10)
    draw_calc_row(f"  Less : SGST {pcts['agency_sgst_tds_pct']:.0f}%", calcs["str_agency_sgst"], indent=10)
    draw_calc_row(f"  Less : CGST {pcts['agency_cgst_tds_pct']:.0f}%", calcs["str_agency_cgst"], indent=10)
    draw_calc_row("  Less : DEDUCTION", calcs["str_agency_deductions_total"], bold=True, indent=10)

    # Section (A - B)
    curr_y -= 4
    draw_calc_row("(A-B)", calcs["str_net_work_done"], bold=True)
    draw_calc_row(f"Administrative and head expense ({pcts['admin_expense_pct']:.2f}%)", calcs["str_admin_expense"], bold=False)

    # Section OUR BILL AMOUNT
    curr_y -= 4
    draw_calc_row("OUR BILL AMOUNT", calcs["str_our_bill_gross"], bold=True)
    draw_calc_row("BASIC", calcs["str_our_basic"], indent=10)
    draw_calc_row("SGST @9%", calcs["str_our_sgst"], indent=10)
    draw_calc_row("CGST @9%", calcs["str_our_cgst"], indent=10)

    # Deductions from Our Bill
    draw_calc_row(f"Less : Income Tax (TDS) @{pcts['it_tds_pct']:.2f}%", calcs["str_it_tds"], indent=10)
    draw_calc_row(f"Less : Retention Money ({pcts['retention_pct']:.1f}%)", calcs["str_retention"], indent=10)
    draw_calc_row(f"Less : Labour Cess {pcts['labour_cess_pct']:.2f}%", calcs["str_labour_cess"], indent=10)
    draw_calc_row(f"Less : Testing Fee ({pcts['testing_fee_pct']:.2f}%)", calcs["str_testing_fee"], indent=10)
    draw_calc_row("Round off Rs.", calcs["str_round_off"], indent=10, show_rs=False)

    # Final Net Amount Payable
    curr_y -= 2
    c.setLineWidth(0.6)
    c.line(COL_DESC_X, curr_y - 2, M_R - 10, curr_y - 2)
    curr_y -= 2
    draw_calc_row("Net Amount Payable", calcs["str_net_payable"], bold=True)
    curr_y -= 2
    c.line(COL_DESC_X, curr_y - 2, M_R - 10, curr_y - 2)

    # ── Amount in Words ───────────────────────────────────────────────────────
    curr_y -= 18.0
    c.setFont(B, 8.5)
    c.drawString(COL_DESC_X, curr_y, "Amount in Words:")
    c.setFont(R, 8.5)
    words = calcs["amount_in_words"]
    c.drawString(COL_DESC_X + 90, curr_y, words)

    # ── Signature Block ───────────────────────────────────────────────────────
    sig_y = M_B + 65.0
    c.setFont(B, 9.0)
    c.drawRightString(M_R - 25, sig_y, f"For.: {contractor}")

    # Embed Stamp if requested
    include_stamp = mop_data.get("include_stamp", True)
    if include_stamp:
        stamps_dir = os.path.join(BASE_DIR, "Stamps")
        stamp_file = None
        if os.path.exists(stamps_dir):
            for fn in os.listdir(stamps_dir):
                if fn.endswith(".png") and any(k.lower() in fn.lower() for k in contractor.split()[:2]):
                    stamp_file = os.path.join(stamps_dir, fn)
                    break
        if stamp_file and os.path.exists(stamp_file):
            try:
                c.drawImage(
                    stamp_file,
                    M_R - 145,
                    sig_y - 48,
                    width=115,
                    height=52,
                    mask="auto",
                    preserveAspectRatio=True
                )
            except Exception:
                pass

    c.setFont(B, 8.5)
    c.drawRightString(M_R - 25, M_B + 20.0, "Authorised Signatory")
    c.setFont(R, 8.0)
    c.drawRightString(M_R - 25, M_B + 10.0, "Contractor")

    c.showPage()
    c.save()
    return output_pdf


if __name__ == "__main__":
    # Test calculation with Excel sample
    sample_amount = 19099731.00
    res = calculate_mop(sample_amount)
    print("=== MOP SAMPLE CALCULATION ===")
    print("Total Work Done (A):", res["str_gross_amount"])
    print("Agency Deductions (B):", res["str_agency_deductions_total"])
    print("Net (A-B):", res["str_net_work_done"])
    print("Admin Expense (3.25%):", res["str_admin_expense"])
    print("Our Bill Amount:", res["str_our_bill_gross"])
    print("Net Amount Payable:", res["str_net_payable"])
    print("Amount in Words:", res["amount_in_words"])

    # Test PDF generation
    out = os.path.join(BASE_DIR, "outputs", "test_mop_sample.pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    draw_mop_pdf({
        "contractor_name": "Jay Khodiyar Enterprise",
        "contractor_gstin": "24BJHPP5061K1ZZ",
        "agency_name": "JNP INFRASTRUCTURE",
        "agency_gstin": "24AADFJ3113C1Z6",
        "work_name": "Providing & Laying Sewerage Network at Nikol, Ahmedabad",
        "bill_sr_no": "15/26-27",
        "date_of_record": "09/07/2026",
        "ra_bill_no": "RA BILL NO. 01",
        "ra_bill_date": "09/07/2026",
        "amount": sample_amount,
        "include_stamp": True
    }, out)
    print("Test PDF generated successfully:", out)
