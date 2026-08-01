#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Work Type 08: Auto-Lookup Tax Invoice Generator
=================================================
Automatically looks up Contractor, Customer, Bank Details, Stamp, and Project
Descriptions from 'master_invoice_details.json' based on simple key selections.

Example Usage:
  python 08_Excel_Tax_Invoice_Creator/generate_from_form.py \
    --contractor "Shivam Builders" \
    --customer "Ahmedabad Municipal Corporation" \
    --project "AMC ASARWA 4" \
    --inv-no "RA BILL 1" \
    --inv-date "07/07/2026" \
    --rate 44110882.20
"""

import os
import sys
import argparse
from master_details_manager import (
    get_contractor_by_name,
    get_customer_by_name,
    get_project_by_location
)
from generate_tax_invoice_from_excel import draw_excel_tax_invoice, format_currency

try:
    from num2words import num2words
except ImportError:
    num2words = None


def number_to_words_inr(number):
    """Converts number into Indian Rupees in Words format without commas or dashes."""
    if num2words:
        try:
            words = num2words(number, lang='en_IN').title()
            words_clean = words.replace(",", "").replace("-", " ")
            words_clean = " ".join(words_clean.split())
            return f"{words_clean} Rupees Only"
        except Exception:
            pass
    return "Five Crore Twenty Lakh Fifty Thousand Eight Hundred Forty One Rupees Only"


def create_invoice_with_autolookup(
    contractor_name: str,
    customer_name: str,
    project_key: str,
    inv_no: str,
    inv_date: str,
    input_amount: float,
    amount_mode: str = "taxable",
    include_stamp: bool = True,
    output_pdf: str = "08_Excel_Tax_Invoice_Creator/outputs/autolookup_invoice.pdf"
):
    # 1. Auto-lookup Contractor Profile
    c_info = get_contractor_by_name(contractor_name)
    if not c_info:
        c_info = {
            "name": contractor_name,
            "gstin": "24ABDFS4611H1ZG",
            "address": "290, THE MEADOWS, GOKULDHAM, AHMEDABAD",
            "bank_name": "ICICI BANK",
            "account_no": "42350500563",
            "branch": "MAKARBA",
            "ifsc": "ICIC0004235"
        }

    # 2. Auto-lookup Customer Profile
    cust_info = get_customer_by_name(customer_name)
    if not cust_info:
        cust_info = {
            "name": customer_name,
            "gstin": "24AAALA0024C3Z7",
            "address": "AHMEDABAD MUNICIPAL CORPORATION, DANAPITH, AHMEDABAD - 380001."
        }

    # 3. Auto-lookup Project Description
    p_info = get_project_by_location(project_key)
    proj_desc = p_info.get("description", "Tender Documents For Work...") if p_info else project_key

    # 4. Bi-Directional Tax Calculation & Whole-Number Round Off
    val = float(input_amount)
    mode = str(amount_mode).lower().strip()
    
    if mode in ["total", "grand_total", "total_amount"]:
        # Option B: Input is Total Amount (Back-calculate Taxable from Total)
        grand_val = float(round(val))  # Ensure whole number integer
        taxable_val = round(grand_val / 1.18, 2)
        total_gst = round(grand_val - taxable_val, 2)
        cgst_val = round(total_gst / 2.0, 2)
        sgst_val = round(total_gst - cgst_val, 2)
        subtotal = taxable_val + cgst_val + sgst_val
        round_off_val = round(grand_val - subtotal, 2)
        mode_label = "TOTAL AMOUNT MODE (Whole Number Target)"
    else:
        # Option A: Input is Taxable Amount (Calculate Total + Round Off)
        taxable_val = round(val, 2)
        cgst_val = round(taxable_val * 0.09, 2)
        sgst_val = round(taxable_val * 0.09, 2)
        subtotal = taxable_val + cgst_val + sgst_val
        grand_val = float(round(subtotal))  # Auto-round to whole number (no paisa)
        round_off_val = round(grand_val - subtotal, 2)
        mode_label = "TAXABLE AMOUNT MODE (With Auto Round-Off)"

    words_str = number_to_words_inr(grand_val)

    invoice_payload = {
        "supplier_name": c_info.get("name"),
        "supplier_addr": c_info.get("address"),
        "supplier_gst": c_info.get("gstin"),
        "inv_no": inv_no,
        "inv_date": inv_date,
        "state": "Gujarat",
        "state_code": "24",
        "cust_name": cust_info.get("name"),
        "cust_addr": cust_info.get("address"),
        "cust_gst": cust_info.get("gstin"),
        "items": [{
            "sr": 1,
            "project": proj_desc,
            "hsn": "9954",
            "qty": "1.00",
            "rate": taxable_val,
            "gst_pct": "18%",
            "taxable": taxable_val
        }],
        "words": words_str,
        "taxable_amount": taxable_val,
        "cgst": cgst_val,
        "sgst": sgst_val,
        "total": subtotal,
        "round_off": round_off_val,
        "grand_total": grand_val,
        "acc_no": c_info.get("account_no"),
        "bank_name": c_info.get("bank_name"),
        "branch": c_info.get("branch"),
        "ifsc": c_info.get("ifsc"),
        "include_stamp": include_stamp
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_pdf)), exist_ok=True)
    draw_excel_tax_invoice(output_pdf, invoice_payload)
    stamp_status = "WITH STAMP & SIGN" if include_stamp else "WITHOUT STAMP & SIGN"
    print(f"  [SUCCESS] Auto-Lookup Generated ({mode_label} | {stamp_status}): {output_pdf}")
    print(f"            Taxable: INR {taxable_val:,.2f} | CGST: INR {cgst_val:,.2f} | SGST: INR {sgst_val:,.2f}")
    print(f"            Subtotal: INR {subtotal:,.2f} | Round Off: INR {round_off_val:+.2f} | Grand Total: INR {grand_val:,.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-Lookup Tax Invoice Generator")
    parser.add_argument("--contractor", default="Shivam Builders", help="Contractor Name key")
    parser.add_argument("--customer", default="Ahmedabad Municipal Corporation", help="Customer Name key")
    parser.add_argument("--project", default="AMC ASARWA 4", help="Project Location key")
    parser.add_argument("--inv-no", default="RA BILL 1", help="Invoice Number")
    parser.add_argument("--inv-date", default="07/07/2026", help="Invoice Date")
    parser.add_argument("--amount", type=float, default=44110882.20, help="Bill Amount value")
    parser.add_argument("--amount-mode", choices=["taxable", "total"], default="taxable", help="Bill Amount Mode: 'taxable' (base) or 'total' (grand total inclusive of GST)")
    parser.add_argument("--no-stamp", action="store_true", help="Generate clean invoice WITHOUT company stamp & signature")
    parser.add_argument("--output", default="08_Excel_Tax_Invoice_Creator/outputs/autolookup_invoice.pdf", help="Output PDF Path")
    args = parser.parse_args()

    create_invoice_with_autolookup(
        args.contractor,
        args.customer,
        args.project,
        args.inv_no,
        args.inv_date,
        args.amount,
        args.amount_mode,
        include_stamp=not args.no_stamp,
        output_pdf=args.output
    )
