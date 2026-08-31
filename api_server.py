# -*- coding: utf-8 -*-
"""
Tax Invoice Generator — API Backend Server
Runs on Port 8031. Serves contractor/customer/project data and generates PDF invoices.
"""
import sys
import os
import json
import datetime
import requests
import base64
import tempfile

# Self-contained directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Add parent path fallback
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '08_Excel_Tax_Invoice_Creator'))
if os.path.exists(PARENT_DIR):
    sys.path.insert(1, PARENT_DIR)

from flask import Flask, jsonify, request, send_file

# Import the invoice, MOP, and E-Invoice generators
from generate_from_form import create_invoice_with_autolookup
from mop_generator import calculate_mop, draw_mop_pdf
from einv_generator import generate_einv_pdf

# Load master details
MASTER_JSON = os.path.join(BASE_DIR, 'master_invoice_details.json')
if not os.path.exists(MASTER_JSON):
    MASTER_JSON = os.path.join(PARENT_DIR, 'master_invoice_details.json')

with open(MASTER_JSON, 'r', encoding='utf-8') as f:
    MASTER = json.load(f)

app = Flask(__name__)

try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
        return response


# ─── Helper: Indian Number Formatting ────────────────────────────────────────
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


# ─── GET /api/contractors ─────────────────────────────────────────────────────
@app.route('/contractors', methods=['GET'])
@app.route('/api/contractors', methods=['GET'])
def get_contractors():
    include_all = request.args.get('all', 'false').lower() in ['true', '1']
    names = [c['name'] for c in MASTER.get('contractors', []) if include_all or c.get('active', True) != False]
    return jsonify(names)


@app.route('/contractors/full', methods=['GET'])
@app.route('/api/contractors/full', methods=['GET'])
def get_contractors_full():
    return jsonify(MASTER.get('contractors', []))


# ─── GET /api/customers ───────────────────────────────────────────────────────
@app.route('/customers', methods=['GET'])
@app.route('/api/customers', methods=['GET'])
def get_customers():
    include_all = request.args.get('all', 'false').lower() in ['true', '1']
    names = [c['name'] for c in MASTER.get('customers', []) if include_all or c.get('active', True) != False]
    return jsonify(names)


@app.route('/customers/full', methods=['GET'])
@app.route('/api/customers/full', methods=['GET'])
def get_customers_full():
    return jsonify(MASTER.get('customers', []))


# ─── GET /api/projects ────────────────────────────────────────────────────────
@app.route('/projects', methods=['GET'])
@app.route('/api/projects', methods=['GET'])
def get_projects():
    include_all = request.args.get('all', 'false').lower() in ['true', '1']
    projects = [
        {'key': p['location_key'], 'label': p['location_key']}
        for p in MASTER.get('projects', [])
        if include_all or p.get('active', True) != False
    ]
    return jsonify(projects)


@app.route('/projects/full', methods=['GET'])
@app.route('/api/projects/full', methods=['GET'])
def get_projects_full():
    return jsonify(MASTER.get('projects', []))


# ─── POST /api/master/toggle-status ───────────────────────────────────────────
@app.route('/master/toggle-status', methods=['POST'])
@app.route('/api/master/toggle-status', methods=['POST'])
@app.route('/toggle-status', methods=['POST'])
@app.route('/api/toggle-status', methods=['POST'])
def toggle_master_status():
    """Toggles active/inactive status for contractors, customers, or projects."""
    data = request.json or {}
    cat = str(data.get('category') or data.get('type') or '').lower().strip()
    item_id = str(data.get('name') or data.get('key') or data.get('id') or '').strip()
    new_active = bool(data.get('active', True))

    if cat in ['contractor', 'contractors']:
        items = MASTER.get('contractors', [])
        target = next((c for c in items if c.get('name') == item_id), None)
    elif cat in ['customer', 'customers']:
        items = MASTER.get('customers', [])
        target = next((c for c in items if c.get('name') == item_id), None)
    elif cat in ['project', 'projects']:
        items = MASTER.get('projects', [])
        target = next((p for p in items if p.get('location_key') == item_id), None)
    else:
        return jsonify({'error': 'Invalid category'}), 400

    if not target:
        return jsonify({'error': f'Item "{item_id}" not found in {cat}'}), 404

    target['active'] = new_active
    save_master_json()
    return jsonify({'status': 'success', 'category': cat, 'id': item_id, 'active': new_active})


# ─── POST /api/preview ────────────────────────────────────────────────────────
@app.route('/preview', methods=['POST'])
@app.route('/api/preview', methods=['POST'])
def preview_invoice():
    """Returns calculated tax figures without generating PDF."""
    data = request.json or {}
    amount = float(data.get('amount', 0))
    mode = str(data.get('amount_mode', 'taxable')).lower().strip()
    custom_ro = data.get('custom_round_off')

    if mode in ['total', 'grand_total', 'total_amount']:
        grand_val = float(round(amount))
        taxable_val = round(grand_val / 1.18, 2)
        total_gst = round(grand_val - taxable_val, 2)
        cgst_val = round(total_gst / 2.0, 2)
        sgst_val = round(total_gst - cgst_val, 2)
        subtotal = taxable_val + cgst_val + sgst_val
        if custom_ro is not None and str(custom_ro).strip() != '':
            try:
                round_off = round(float(custom_ro), 2)
                grand_val = round(subtotal + round_off, 2)
            except Exception:
                round_off = round(grand_val - subtotal, 2)
        else:
            round_off = round(grand_val - subtotal, 2)
    else:
        taxable_val = round(amount, 2)
        cgst_val = round(taxable_val * 0.09, 2)
        sgst_val = round(taxable_val * 0.09, 2)
        subtotal = taxable_val + cgst_val + sgst_val
        if custom_ro is not None and str(custom_ro).strip() != '':
            try:
                round_off = round(float(custom_ro), 2)
                grand_val = round(subtotal + round_off, 2)
            except Exception:
                grand_val = float(round(subtotal))
                round_off = round(grand_val - subtotal, 2)
        else:
            grand_val = float(round(subtotal))
            round_off = round(grand_val - subtotal, 2)

    return jsonify({
        'taxable': fmt_indian(taxable_val),
        'cgst': fmt_indian(cgst_val),
        'sgst': fmt_indian(sgst_val),
        'subtotal': fmt_indian(subtotal),
        'round_off': f"{round_off:+.2f}",
        'grand_total': fmt_indian(grand_val),
        'taxable_raw': taxable_val,
        'cgst_raw': cgst_val,
        'sgst_raw': sgst_val,
        'round_off_raw': round_off,
        'grand_total_raw': grand_val,
    })


# ─── POST /api/generate ───────────────────────────────────────────────────────
@app.route('/generate', methods=['POST'])
@app.route('/api/generate', methods=['POST'])
def generate_invoice():
    """Generates Tax or Proforma Invoice PDF and returns it as download or JSON."""
    data = request.json or {}

    contractor = data.get('contractor', 'Shivam Builders')
    customer = data.get('customer', 'Ahmedabad Municipal Corporation')
    project = data.get('project', 'AMC ASARWA 4')
    inv_no = data.get('inv_no', 'RA BILL 1')
    inv_date = data.get('inv_date', datetime.date.today().strftime('%d/%m/%Y'))
    amount = float(data.get('amount', 0))
    amount_mode = data.get('amount_mode', 'taxable')
    include_stamp = bool(data.get('include_stamp', True))
    custom_round_off = data.get('custom_round_off')
    doc_type = data.get('doc_type', 'tax_invoice')
    if str(doc_type).lower().strip() in ['mop', 'memorandum_of_payment', 'memorandum-of-payment']:
        return api_mop_generate()
    if str(doc_type).lower().strip() in ['e_invoice', 'einvoice', 'e-invoice']:
        return api_einv_generate()

    is_proforma = str(doc_type).lower().strip() in ['proforma', 'proforma_invoice', 'proforma-invoice']
    doc_title_label = "Proforma Invoice" if is_proforma else "Tax Invoice"
    doc_suffix = "Proforma_Invoice" if is_proforma else "Tax_Invoice"

    # Build dynamic output filename (e.g. AMC_Kali_Lake_RA_BILL_1_Tax_Invoice.pdf / Proforma_Invoice.pdf)
    safe_project = project.strip().replace('/', '-').replace('\\', '-').replace(' ', '_')
    safe_inv = inv_no.strip().replace('/', '-').replace('\\', '-').replace(' ', '_')
    fname = f"{safe_project}_{safe_inv}_{doc_suffix}.pdf"

    outputs_dir = os.path.join(BASE_DIR, 'outputs')
    try:
        os.makedirs(outputs_dir, exist_ok=True)
        test_file = os.path.join(outputs_dir, '.write_test')
        with open(test_file, 'w') as tf:
            tf.write('ok')
        os.remove(test_file)
    except Exception:
        outputs_dir = tempfile.gettempdir()
    output_path = os.path.join(outputs_dir, fname)

    try:
        create_invoice_with_autolookup(
            contractor_name=contractor,
            customer_name=customer,
            project_key=project,
            inv_no=inv_no,
            inv_date=inv_date,
            input_amount=amount,
            amount_mode=amount_mode,
            include_stamp=include_stamp,
            output_pdf=output_path,
            doc_type=doc_type,
            custom_round_off=custom_round_off
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    import base64
    import requests

    user_id = data.get('user_id') or data.get('chat_id')
    return_json = data.get('return_json') or bool(user_id) or request.headers.get('Accept') == 'application/json'

    # Check if Telegram chat delivery is requested
    sent_to_telegram = False
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        # Check local .env or bot_credentials.json if running locally
        _env = os.path.join(BASE_DIR, '.env')
        if os.path.exists(_env):
            try:
                with open(_env, 'r', encoding='utf-8') as _f:
                    for _l in _f:
                        if _l.strip().startswith('TELEGRAM_BOT_TOKEN='):
                            bot_token = _l.strip().split('=', 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
        if not bot_token:
            _creds = os.path.join(BASE_DIR, 'bot_credentials.json')
            if os.path.exists(_creds):
                try:
                    with open(_creds, 'r', encoding='utf-8') as _f:
                        bot_token = json.load(_f).get('telegram_bot_token')
                except Exception:
                    pass
    
    if user_id and bot_token and bot_token != "YOUR_BOT_TOKEN_FROM_BOTFATHER":
        try:
            telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            icon = "📋" if is_proforma else "🧾"
            with open(output_path, 'rb') as f:
                caption = f"{icon} *{doc_title_label} Generated*\n• Invoice No: `{inv_no}`\n• Project: `{project}`\n• Contractor: `{contractor}`"
                resp = requests.post(
                    telegram_api_url,
                    data={'chat_id': user_id, 'caption': caption, 'parse_mode': 'Markdown'},
                    files={'document': (fname, f, 'application/pdf')},
                    timeout=8
                )
                if resp.status_code == 200:
                    sent_to_telegram = True
        except Exception as tel_err:
            print(f"[-] Failed to send document via Telegram Bot API: {tel_err}")

    # Read base64 string for mobile webview inline viewer
    with open(output_path, 'rb') as f:
        pdf_bytes = f.read()
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        data_url = f"data:application/pdf;base64,{pdf_b64}"

    if return_json:
        return jsonify({
            'status': 'success',
            'filename': fname,
            'doc_type': doc_type,
            'doc_title': doc_title_label,
            'pdf_base64': pdf_b64,
            'data_url': data_url,
            'sent_to_telegram': sent_to_telegram
        })

    return send_file(
        output_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=fname
    )


# ─── GET & POST /api/mop/config ──────────────────────────────────────────────
@app.route('/mop/config', methods=['GET', 'POST'])
@app.route('/api/mop/config', methods=['GET', 'POST'])
def handle_mop_config():
    """Retrieves or saves contractor/project specific MOP percentage rules."""
    mop_rules = MASTER.get('mop_rules', {
        'default': {
            'agency_tds_pct': 2.0,
            'agency_sgst_tds_pct': 1.0,
            'agency_cgst_tds_pct': 1.0,
            'admin_expense_pct': 3.25,
            'it_tds_pct': 1.0,
            'retention_pct': 2.0,
            'labour_cess_pct': 1.0,
            'testing_fee_pct': 0.5
        },
        'contractor_overrides': {},
        'project_overrides': {}
    })

    if request.method == 'POST':
        data = request.json or {}
        contractor = data.get('contractor')
        project = data.get('project')
        new_config = data.get('config') or {}

        if contractor and 'contractor_overrides' in mop_rules:
            mop_rules['contractor_overrides'][contractor] = new_config
        elif project and 'project_overrides' in mop_rules:
            mop_rules['project_overrides'][project] = new_config
        else:
            mop_rules['default'].update(new_config)

        MASTER['mop_rules'] = mop_rules
        save_master_json()
        return jsonify({'status': 'success', 'mop_rules': mop_rules})

    # GET Request: resolve effective config for contractor & project
    contractor = request.args.get('contractor', '')
    project = request.args.get('project', '')

    effective = dict(mop_rules.get('default', {}))
    if contractor and contractor in mop_rules.get('contractor_overrides', {}):
        effective.update(mop_rules['contractor_overrides'][contractor])
    if project and project in mop_rules.get('project_overrides', {}):
        effective.update(mop_rules['project_overrides'][project])

    return jsonify({
        'effective_config': effective,
        'all_rules': mop_rules
    })


# ─── POST /api/mop/calculate ──────────────────────────────────────────────────
@app.route('/mop/calculate', methods=['POST'])
@app.route('/api/mop/calculate', methods=['POST'])
def api_mop_calculate():
    """Calculates all MOP breakdowns dynamically from input amount and percentages."""
    data = request.json or {}
    amount = float(data.get('amount', 0))
    contractor = data.get('contractor', '')
    project = data.get('project', '')
    user_config = data.get('config') or {}

    # Resolve defaults
    mop_rules = MASTER.get('mop_rules', {})
    effective = dict(mop_rules.get('default', {
        'agency_tds_pct': 2.0,
        'agency_sgst_tds_pct': 1.0,
        'agency_cgst_tds_pct': 1.0,
        'admin_expense_pct': 3.25,
        'it_tds_pct': 1.0,
        'retention_pct': 2.0,
        'labour_cess_pct': 1.0,
        'testing_fee_pct': 0.5
    }))

    if contractor and contractor in mop_rules.get('contractor_overrides', {}):
        effective.update(mop_rules['contractor_overrides'][contractor])
    if project and project in mop_rules.get('project_overrides', {}):
        effective.update(mop_rules['project_overrides'][project])

    # Overlay user custom percentages
    effective.update(user_config)
    custom_round_off = data.get('custom_round_off')

    calcs = calculate_mop(amount, effective, custom_round_off)
    return jsonify({
        'status': 'success',
        'calculations': calcs,
        'config_used': effective
    })


# ─── POST /api/mop/generate ───────────────────────────────────────────────────
@app.route('/mop/generate', methods=['POST'])
@app.route('/api/mop/generate', methods=['POST'])
def api_mop_generate():
    """Generates MOP (Memorandum of Payment) Vector PDF."""
    data = request.json or {}

    contractor_name = data.get('contractor', 'Jay Khodiyar Enterprise')
    agency_name = data.get('agency', data.get('customer', 'JNP INFRASTRUCTURE'))
    project_key = data.get('project', 'AMC ASARWA 4')
    inv_no = data.get('inv_no', 'RA BILL 1')
    inv_date = data.get('inv_date', datetime.date.today().strftime('%d/%m/%Y'))
    bill_sr_no = data.get('bill_sr_no', '15/26-27')
    date_of_record = data.get('date_of_record', inv_date)
    amount = float(data.get('amount', 0))
    include_stamp = bool(data.get('include_stamp', True))
    custom_round_off = data.get('custom_round_off')
    user_config = data.get('config') or {}

    # Lookup GSTINs
    c_info = next((c for c in MASTER.get('contractors', []) if c['name'] == contractor_name), None)
    contractor_gstin = c_info.get('gstin', '') if c_info else ''

    a_info = next((c for c in MASTER.get('contractors', []) if c['name'] == agency_name), None)
    if not a_info:
        a_info = next((c for c in MASTER.get('customers', []) if c['name'] == agency_name), None)
    agency_gstin = a_info.get('gstin', '') if a_info else ''

    p_info = next((p for p in MASTER.get('projects', []) if p['location_key'] == project_key), None)
    work_name = p_info.get('description', project_key) if p_info else project_key

    # Resolve Effective Percentage Rules
    mop_rules = MASTER.get('mop_rules', {})
    effective = dict(mop_rules.get('default', {
        'agency_tds_pct': 2.0,
        'agency_sgst_tds_pct': 1.0,
        'agency_cgst_tds_pct': 1.0,
        'admin_expense_pct': 3.25,
        'it_tds_pct': 1.0,
        'retention_pct': 2.0,
        'labour_cess_pct': 1.0,
        'testing_fee_pct': 0.5
    }))
    if contractor_name and contractor_name in mop_rules.get('contractor_overrides', {}):
        effective.update(mop_rules['contractor_overrides'][contractor_name])
    if project_key and project_key in mop_rules.get('project_overrides', {}):
        effective.update(mop_rules['project_overrides'][project_key])
    effective.update(user_config)

    calcs = calculate_mop(amount, effective, custom_round_off)

    safe_project = project_key.strip().replace('/', '-').replace('\\', '-').replace(' ', '_')
    safe_inv = inv_no.strip().replace('/', '-').replace('\\', '-').replace(' ', '_')
    fname = f"{safe_project}_{safe_inv}_MOP_Statement.pdf"

    outputs_dir = os.path.join(BASE_DIR, 'outputs')
    try:
        os.makedirs(outputs_dir, exist_ok=True)
        test_file = os.path.join(outputs_dir, '.write_test')
        with open(test_file, 'w') as tf:
            tf.write('ok')
        os.remove(test_file)
    except Exception:
        outputs_dir = tempfile.gettempdir()
    output_path = os.path.join(outputs_dir, fname)

    mop_payload = {
        "contractor_name": contractor_name,
        "contractor_gstin": contractor_gstin,
        "agency_name": agency_name,
        "agency_gstin": agency_gstin,
        "work_name": work_name,
        "bill_sr_no": bill_sr_no,
        "date_of_record": date_of_record,
        "ra_bill_no": inv_no,
        "ra_bill_date": inv_date,
        "amount": amount,
        "config": effective,
        "calculations": calcs,
        "include_stamp": include_stamp
    }

    try:
        draw_mop_pdf(mop_payload, output_path)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    user_id = data.get('user_id') or data.get('chat_id')
    return_json = data.get('return_json') or bool(user_id) or request.headers.get('Accept') == 'application/json'

    sent_to_telegram = False
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        _env = os.path.join(BASE_DIR, '.env')
        if os.path.exists(_env):
            try:
                with open(_env, 'r', encoding='utf-8') as _f:
                    for _l in _f:
                        if _l.strip().startswith('TELEGRAM_BOT_TOKEN='):
                            bot_token = _l.strip().split('=', 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
        if not bot_token:
            _creds = os.path.join(BASE_DIR, 'bot_credentials.json')
            if os.path.exists(_creds):
                try:
                    with open(_creds, 'r', encoding='utf-8') as _f:
                        bot_token = json.load(_f).get('telegram_bot_token')
                except Exception:
                    pass

    if user_id and bot_token and bot_token != "YOUR_BOT_TOKEN_FROM_BOTFATHER":
        try:
            telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            with open(output_path, 'rb') as f:
                caption = f"📑 *MOP (Memorandum of Payment) Generated*\n• Bill No: `{inv_no}`\n• Project: `{project_key}`\n• Net Payable: `INR {calcs['str_net_payable']}`"
                resp = requests.post(
                    telegram_api_url,
                    data={'chat_id': user_id, 'caption': caption, 'parse_mode': 'Markdown'},
                    files={'document': (fname, f, 'application/pdf')},
                    timeout=8
                )
                if resp.status_code == 200:
                    sent_to_telegram = True
        except Exception as tel_err:
            print(f"[-] Failed to send MOP via Telegram Bot API: {tel_err}")

    with open(output_path, 'rb') as f:
        pdf_bytes = f.read()
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        data_url = f"data:application/pdf;base64,{pdf_b64}"

    if return_json:
        return jsonify({
            'status': 'success',
            'filename': fname,
            'doc_type': 'mop',
            'doc_title': 'Memorandum of Payment',
            'pdf_base64': pdf_b64,
            'data_url': data_url,
            'calculations': calcs,
            'sent_to_telegram': sent_to_telegram
        })

    return send_file(
        output_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=fname
    )


# ─── POST /api/einv/generate ──────────────────────────────────────────────────
@app.route('/einv/generate', methods=['POST'])
@app.route('/api/einv/generate', methods=['POST'])
def api_einv_generate():
    """Generates NIC Standard E-Invoice Vector PDF."""
    data = request.json or {}

    contractor_name = data.get('contractor', 'JNP INFRASTRUCTURE')
    customer_name = data.get('customer', 'AHMEDABAD MUNICIPAL CORPORATION')
    project_key = data.get('project', 'AMC  Kali Lake')
    inv_no = data.get('inv_no', '2026/27-JNP-1')
    inv_date = data.get('inv_date', datetime.date.today().strftime('%d/%m/%Y'))
    inv_time = data.get('inv_time') or data.get('time')
    amount = float(data.get('amount', 0))
    amount_mode = data.get('amount_mode', 'taxable')
    hsn_code = data.get('hsn', '995424')
    custom_round_off = data.get('custom_round_off')

    # Lookup contractor and customer details
    c_info = next((c for c in MASTER.get('contractors', []) if c['name'] == contractor_name), None)
    cust_info = next((c for c in MASTER.get('customers', []) if c['name'] == customer_name), None)

    safe_contractor = (contractor_name or 'Contractor').strip().replace('/', '-').replace('\\', '-').replace(' ', '_')
    safe_inv = (inv_no or 'Doc').strip().replace('/', '-').replace('\\', '-').replace(' ', '_')
    if project_key and project_key.strip():
        safe_project = project_key.strip().replace('/', '-').replace('\\', '-').replace(' ', '_')
        fname = f"{safe_project}_{safe_inv}_E_Invoice.pdf"
    else:
        fname = f"{safe_contractor}_{safe_inv}_E_Invoice.pdf"

    outputs_dir = os.path.join(BASE_DIR, 'outputs')
    try:
        os.makedirs(outputs_dir, exist_ok=True)
    except Exception:
        outputs_dir = tempfile.gettempdir()
    output_path = os.path.join(outputs_dir, fname)

    einv_payload = {
        "contractor": contractor_name,
        "customer": customer_name,
        "contractor_data": c_info or {"name": contractor_name},
        "customer_data": cust_info or {"name": customer_name},
        "project": project_key,
        "inv_no": inv_no,
        "inv_date": inv_date,
        "inv_time": inv_time,
        "amount": amount,
        "amount_mode": amount_mode,
        "hsn": hsn_code,
        "custom_round_off": custom_round_off
    }

    try:
        out_file, calcs = generate_einv_pdf(einv_payload, output_path)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    user_id = data.get('user_id') or data.get('chat_id')
    return_json = data.get('return_json') or bool(user_id) or request.headers.get('Accept') == 'application/json'

    sent_to_telegram = False
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        _env = os.path.join(BASE_DIR, '.env')
        if os.path.exists(_env):
            try:
                with open(_env, 'r', encoding='utf-8') as _f:
                    for _l in _f:
                        if _l.strip().startswith('TELEGRAM_BOT_TOKEN='):
                            bot_token = _l.strip().split('=', 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
        if not bot_token:
            _creds = os.path.join(BASE_DIR, 'bot_credentials.json')
            if os.path.exists(_creds):
                try:
                    with open(_creds, 'r', encoding='utf-8') as _f:
                        bot_token = json.load(_f).get('telegram_bot_token')
                except Exception:
                    pass

    if user_id and bot_token and bot_token != "YOUR_BOT_TOKEN_FROM_BOTFATHER":
        try:
            telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            with open(output_path, 'rb') as f:
                caption = f"⚡ *E-Invoice (NIC Standard) Generated*\n• Invoice No: `{inv_no}`\n• IRN: `{calcs['irn'][:16]}...`\n• Total: `INR {calcs['total_inv_amt']}`"
                resp = requests.post(
                    telegram_api_url,
                    data={'chat_id': user_id, 'caption': caption, 'parse_mode': 'Markdown'},
                    files={'document': (fname, f, 'application/pdf')},
                    timeout=8
                )
                if resp.status_code == 200:
                    sent_to_telegram = True
        except Exception as tel_err:
            print(f"[-] Failed to send E-Invoice via Telegram Bot API: {tel_err}")

    with open(output_path, 'rb') as f:
        pdf_bytes = f.read()
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        data_url = f"data:application/pdf;base64,{pdf_b64}"

    if return_json:
        return jsonify({
            'status': 'success',
            'filename': fname,
            'doc_type': 'e_invoice',
            'doc_title': 'E-Invoice (NIC Standard)',
            'pdf_base64': pdf_b64,
            'data_url': data_url,
            'calculations': calcs,
            'sent_to_telegram': sent_to_telegram
        })

    return send_file(
        output_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=fname
    )


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Tax, Proforma, MOP & E-Invoice Generator API', 'port': 8031})


def save_master_json():
    """Helper to save updated MASTER dictionary back to master_invoice_details.json."""
    paths_to_update = [
        MASTER_JSON,
        os.path.join(BASE_DIR, 'master_invoice_details.json')
    ]
    for p in set(paths_to_update):
        try:
            if os.path.exists(os.path.dirname(p)):
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(MASTER, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


# ─── POST /api/add-contractor ────────────────────────────────────────────────
@app.route('/add-contractor', methods=['POST'])
@app.route('/api/add-contractor', methods=['POST'])
def add_contractor():
    try:
        data = request.json or request.form or {}
        name = data.get('name')
        if not name:
            return jsonify({'error': 'Contractor name is required'}), 400

        gstin = data.get('gstin', '')
        address = data.get('address', '')
        bank_name = data.get('bank_name', '')
        account_no = data.get('account_no', '')
        branch = data.get('branch', '')
        ifsc = data.get('ifsc', '')

        # Check for uploaded stamp file
        stamp_file = request.files.get('stamp_file') if request.files else None
        if stamp_file and stamp_file.filename:
            stamps_dir = os.path.join(BASE_DIR, 'Stamps')
            os.makedirs(stamps_dir, exist_ok=True)
            ext = os.path.splitext(stamp_file.filename)[1].lower() or '.png'
            safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            stamp_save_path = os.path.join(stamps_dir, f"{safe_name}{ext}")
            stamp_file.save(stamp_save_path)

        contractors = MASTER.get('contractors', [])
        existing = next((c for c in contractors if c.get('name') == name), None)
        is_active = bool(data.get('active', existing.get('active', True) if existing else True))
        new_entry = {
            'name': name,
            'gstin': gstin,
            'address': address,
            'bank_name': bank_name,
            'account_no': account_no,
            'branch': branch,
            'ifsc': ifsc,
            'active': is_active
        }

        if existing:
            existing.update(new_entry)
        else:
            contractors.append(new_entry)

        MASTER['contractors'] = contractors
        save_master_json()

        return jsonify({'status': 'success', 'contractor': new_entry})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── POST /api/add-customer ──────────────────────────────────────────────────
@app.route('/add-customer', methods=['POST'])
@app.route('/api/add-customer', methods=['POST'])
def add_customer():
    try:
        data = request.json or request.form or {}
        name = data.get('name')
        if not name:
            return jsonify({'error': 'Customer name is required'}), 400

        gstin = data.get('gstin', '')
        address = data.get('address', '')

        customers = MASTER.get('customers', [])
        existing = next((c for c in customers if c.get('name') == name), None)
        is_active = bool(data.get('active', existing.get('active', True) if existing else True))
        new_entry = {'name': name, 'gstin': gstin, 'address': address, 'active': is_active}

        if existing:
            existing.update(new_entry)
        else:
            customers.append(new_entry)

        MASTER['customers'] = customers
        save_master_json()

        return jsonify({'status': 'success', 'customer': new_entry})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── POST /api/add-project ───────────────────────────────────────────────────
@app.route('/add-project', methods=['POST'])
@app.route('/api/add-project', methods=['POST'])
def add_project():
    try:
        data = request.json or request.form or {}
        location_key = data.get('location_key')
        description = data.get('description')

        if not location_key or not description:
            return jsonify({'error': 'Project location_key and description are required'}), 400

        projects = MASTER.get('projects', [])
        existing = next((p for p in projects if p.get('location_key') == location_key), None)
        is_active = bool(data.get('active', existing.get('active', True) if existing else True))
        new_entry = {
            'location_key': location_key,
            'description': description,
            'description_caps': description.upper(),
            'active': is_active
        }

        if existing:
            existing.update(new_entry)
        else:
            projects.append(new_entry)

        MASTER['projects'] = projects
        save_master_json()

        return jsonify({'status': 'success', 'project': new_entry})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Telegram Webhook Routes (Vercel Serverless 24/7 Bot) ─────────────────────
@app.route('/webhook', methods=['POST'])
@app.route('/api/webhook', methods=['POST'])
def telegram_webhook():
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify({'status': 'no_data'}), 200

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            _env = os.path.join(BASE_DIR, '.env')
            if os.path.exists(_env):
                try:
                    with open(_env, 'r', encoding='utf-8') as _f:
                        for _l in _f:
                            if _l.strip().startswith('TELEGRAM_BOT_TOKEN='):
                                bot_token = _l.strip().split('=', 1)[1].strip().strip('"').strip("'")
                except Exception:
                    pass

        if not bot_token:
            return jsonify({'status': 'bot_token_missing'}), 200

        message = update.get('message') or update.get('edited_message')
        if not message:
            return jsonify({'status': 'ignored'}), 200

        chat_id = message.get('chat', {}).get('id')
        user_first_name = message.get('from', {}).get('first_name', 'there')
        text = (message.get('text') or '').strip()

        # Handle WebApp Data (When PDF generated inside Mini App)
        web_app_data = message.get('web_app_data')
        if web_app_data:
            try:
                raw_data = json.loads(web_app_data.get('data', '{}'))
                contractor = raw_data.get('contractor', '')
                customer = raw_data.get('customer', '')
                project = raw_data.get('project', '')
                inv_no = raw_data.get('inv_no', 'INV-01')
                inv_date = raw_data.get('inv_date', '')
                amount = float(raw_data.get('amount', 0))
                amount_mode = raw_data.get('amount_mode', 'taxable')
                include_stamp = raw_data.get('include_stamp', True)
                doc_type = raw_data.get('doc_type', 'tax_invoice')
                is_proforma = doc_type == 'proforma_invoice'
                doc_title_label = "Proforma Invoice" if is_proforma else "Tax Invoice"

                custom_ro = raw_data.get('custom_round_off')
                if custom_ro is not None and str(custom_ro).strip() != '':
                    try:
                        custom_round_off = float(custom_ro)
                    except Exception:
                        custom_round_off = None
                else:
                    custom_round_off = None

                # Generate invoice PDF
                safe_project = "".join(c for c in project if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "Project"
                safe_inv = "".join(c for c in inv_no if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "Invoice"
                file_suffix = "Proforma_Invoice" if is_proforma else "Tax_Invoice"
                fname = f"{safe_project}_{safe_inv}_{file_suffix}.pdf"

                import tempfile
                output_dir = os.path.join(BASE_DIR, 'outputs')
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    test_p = os.path.join(output_dir, '.test')
                    with open(test_p, 'w') as tf:
                        tf.write('1')
                    os.remove(test_p)
                except Exception:
                    output_dir = tempfile.gettempdir()
                output_path = os.path.join(output_dir, fname)

                create_invoice_with_autolookup(
                    contractor_name=contractor,
                    customer_name=customer,
                    project_key=project,
                    inv_no=inv_no,
                    inv_date=inv_date,
                    input_amount=amount,
                    amount_mode=amount_mode,
                    include_stamp=include_stamp,
                    output_pdf=output_path,
                    doc_type=doc_type,
                    custom_round_off=custom_round_off
                )

                # Send document back to user chat
                icon = "📋" if is_proforma else "🧾"
                caption = f"{icon} *{doc_title_label} Generated*\n• Invoice No: `{inv_no}`\n• Project: `{project}`\n• Contractor: `{contractor}`"
                telegram_send_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                with open(output_path, 'rb') as f:
                    requests.post(
                        telegram_send_url,
                        data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'},
                        files={'document': (fname, f, 'application/pdf')},
                        timeout=10
                    )
            except Exception as gen_err:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={'chat_id': chat_id, 'text': f"❌ Error creating invoice: {gen_err}"}
                )
            return jsonify({'status': 'web_app_data_processed'}), 200

        # Handle /start Command
        if text.startswith('/start'):
            webapp_url = os.environ.get("MINI_APP_URL", "https://txtinv.vercel.app")
            welcome_text = (
                f"👋 *Welcome, {user_first_name}!*\n\n"
                f"🧾 *Tax & Proforma Invoice Generator*\n"
                f"Create GST Tax and Proforma Invoices with Indian numbering (`1,00,000`), Round Off and Company Stamps 24/7!\n\n"
                f"Tap the button below to open the Mini App:"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📱 Open Invoice Generator", "web_app": {"url": webapp_url}}]
                ]
            }
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': welcome_text,
                    'parse_mode': 'Markdown',
                    'reply_markup': keyboard
                },
                timeout=5
            )
            return jsonify({'status': 'start_handled'}), 200

        return jsonify({'status': 'ignored'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/set-webhook', methods=['GET', 'POST'])
@app.route('/api/set-webhook', methods=['GET', 'POST'])
def set_webhook():
    """Helper endpoint to register/update Telegram webhook with Vercel URL."""
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            _env = os.path.join(BASE_DIR, '.env')
            if os.path.exists(_env):
                try:
                    with open(_env, 'r', encoding='utf-8') as _f:
                        for _l in _f:
                            if _l.strip().startswith('TELEGRAM_BOT_TOKEN='):
                                bot_token = _l.strip().split('=', 1)[1].strip().strip('"').strip("'")
                except Exception:
                    pass

        if not bot_token:
            return jsonify({'error': 'TELEGRAM_BOT_TOKEN not configured in environment'}), 400

        host = request.host_url.rstrip('/')
        webhook_url = request.args.get('url') or f"{host}/api/webhook"
        if webhook_url.startswith('http://') and 'vercel.app' in webhook_url:
            webhook_url = webhook_url.replace('http://', 'https://')

        resp = requests.get(f"https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}", timeout=10)
        return jsonify({
            'status': 'success',
            'webhook_url': webhook_url,
            'telegram_response': resp.json()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/webhook-info', methods=['GET'])
@app.route('/api/webhook-info', methods=['GET'])
def webhook_info():
    """Helper endpoint to inspect current Telegram webhook status."""
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            _env = os.path.join(BASE_DIR, '.env')
            if os.path.exists(_env):
                try:
                    with open(_env, 'r', encoding='utf-8') as _f:
                        for _l in _f:
                            if _l.strip().startswith('TELEGRAM_BOT_TOKEN='):
                                bot_token = _l.strip().split('=', 1)[1].strip().strip('"').strip("'")
                except Exception:
                    pass

        if not bot_token:
            return jsonify({'error': 'TELEGRAM_BOT_TOKEN not configured'}), 400

        resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("  TAX INVOICE GENERATOR — API BACKEND")
    print("  Port: 8031  |  http://localhost:8031")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8031, debug=False, threaded=True)
