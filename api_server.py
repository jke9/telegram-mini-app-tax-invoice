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

# Import the invoice generator
from generate_from_form import create_invoice_with_autolookup

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
    names = [c['name'] for c in MASTER.get('contractors', [])]
    return jsonify(names)


@app.route('/contractors/full', methods=['GET'])
@app.route('/api/contractors/full', methods=['GET'])
def get_contractors_full():
    return jsonify(MASTER.get('contractors', []))


# ─── GET /api/customers ───────────────────────────────────────────────────────
@app.route('/customers', methods=['GET'])
@app.route('/api/customers', methods=['GET'])
def get_customers():
    names = [c['name'] for c in MASTER.get('customers', [])]
    return jsonify(names)


@app.route('/customers/full', methods=['GET'])
@app.route('/api/customers/full', methods=['GET'])
def get_customers_full():
    return jsonify(MASTER.get('customers', []))


# ─── GET /api/projects ────────────────────────────────────────────────────────
@app.route('/projects', methods=['GET'])
@app.route('/api/projects', methods=['GET'])
def get_projects():
    projects = [
        {'key': p['location_key'], 'label': p['location_key']}
        for p in MASTER.get('projects', [])
    ]
    return jsonify(projects)


@app.route('/projects/full', methods=['GET'])
@app.route('/api/projects/full', methods=['GET'])
def get_projects_full():
    return jsonify(MASTER.get('projects', []))


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
    doc_type = data.get('doc_type', 'tax_invoice')
    custom_ro = data.get('custom_round_off')
    if custom_ro is not None and str(custom_ro).strip() != '':
        try:
            custom_round_off = float(custom_ro)
        except Exception:
            custom_round_off = None
    else:
        custom_round_off = None

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


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Tax & Proforma Invoice Generator API', 'port': 8031})


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
        new_entry = {
            'name': name,
            'gstin': gstin,
            'address': address,
            'bank_name': bank_name,
            'account_no': account_no,
            'branch': branch,
            'ifsc': ifsc
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
        new_entry = {'name': name, 'gstin': gstin, 'address': address}

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
        new_entry = {
            'location_key': location_key,
            'description': description,
            'description_caps': description.upper()
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
