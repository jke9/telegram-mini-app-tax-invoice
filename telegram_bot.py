# -*- coding: utf-8 -*-
"""
Telegram Bot Script for Tax Invoice Generator Mini App
Runs 24/7 online, handles /start command, launches Mini App,
and sends generated PDF directly into Telegram chat inbox!
"""
import os
import sys
import json
import logging
import datetime

# Add parent path to import generator
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from generate_from_form import create_invoice_with_autolookup

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 🤖 Load Telegram Bot Credentials & WebApp URL securely
def load_bot_config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    url = os.environ.get("MINI_APP_URL")

    # 1. Load from local .env file (gitignored)
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k == 'TELEGRAM_BOT_TOKEN' and not token:
                            token = v
                        elif k == 'MINI_APP_URL' and not url:
                            url = v
        except Exception:
            pass

    # 2. Fallback to local bot_credentials.json (gitignored)
    creds_path = os.path.join(BASE_DIR, 'bot_credentials.json')
    if os.path.exists(creds_path):
        try:
            with open(creds_path, 'r', encoding='utf-8') as f:
                c = json.load(f)
                if not token:
                    token = c.get('telegram_bot_token')
                if not url:
                    url = c.get('mini_app_url')
        except Exception:
            pass

    return token or "", url or "http://localhost:8030"

BOT_TOKEN, WEBAPP_URL = load_bot_config()


# ─── /start Command Handler ───────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends start message with button to launch Telegram Mini App."""
    user = update.effective_user
    welcome_text = (
        f"👋 *Welcome, {user.first_name}!*\n\n"
        f"🧾 *Tax & Proforma Invoice Generator Bot*\n"
        f"Generate professional GST Tax and Proforma Invoices in Indian style (`1,00,000`) with Round Off and Company Stamps 24/7 online!\n\n"
        f"Click the button below to open the Mini App:"
    )

    # Inline button opening Mini App
    keyboard = [
        [InlineKeyboardButton("📱 Open Invoice Generator", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ─── WebApp Data Received Handler ─────────────────────────────────────────────
async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when Mini App sends invoice JSON back to Bot chat."""
    try:
        raw_data = update.effective_message.web_app_data.data
        invoice_req = json.loads(raw_data)

        chat_id = update.effective_chat.id

        doc_type = invoice_req.get('doc_type', 'tax_invoice')
        is_proforma = str(doc_type).lower().strip() in ['proforma', 'proforma_invoice', 'proforma-invoice']
        doc_title_label = "Proforma Invoice" if is_proforma else "Tax Invoice"
        file_prefix = "ProformaInvoice" if is_proforma else "TaxInvoice"
        icon = "📋" if is_proforma else "🧾"

        await context.bot.send_message(chat_id, f"⏳ *Generating your {doc_title_label} PDF...*", parse_mode="Markdown")

        # Extract payload
        contractor = invoice_req.get('contractor', 'Shivam Builders')
        customer = invoice_req.get('customer', 'Ahmedabad Municipal Corporation')
        project = invoice_req.get('project', 'AMC ASARWA 4')
        inv_no = invoice_req.get('inv_no', 'RA BILL 1')
        inv_date = invoice_req.get('inv_date', datetime.date.today().strftime('%d/%m/%Y'))
        amount = float(invoice_req.get('amount', 0))
        amount_mode = invoice_req.get('amount_mode', 'taxable')
        include_stamp = bool(invoice_req.get('include_stamp', True))

        # Output PDF path
        safe_inv = inv_no.replace(' ', '_').replace('/', '-').replace('\\', '-')
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = f"{file_prefix}_{safe_inv}_{timestamp}.pdf"
        outputs_dir = os.path.join(BASE_DIR, 'outputs')
        os.makedirs(outputs_dir, exist_ok=True)
        pdf_path = os.path.join(outputs_dir, fname)

        # Generate PDF
        create_invoice_with_autolookup(
            contractor_name=contractor,
            customer_name=customer,
            project_key=project,
            inv_no=inv_no,
            inv_date=inv_date,
            input_amount=amount,
            amount_mode=amount_mode,
            include_stamp=include_stamp,
            output_pdf=pdf_path,
            doc_type=doc_type
        )

        # Send PDF document directly into Telegram chat!
        with open(pdf_path, 'rb') as pdf_file:
            caption = (
                f"✅ *{doc_title_label} Generated Successfully!*\n\n"
                f"🏢 *Contractor:* {contractor}\n"
                f"🏛️ *Customer:* {customer}\n"
                f"📄 *Invoice No:* {inv_no}\n"
                f"📅 *Date:* {inv_date}\n"
                f"✒️ *Stamp:* {'With Stamp & Sign' if include_stamp else 'Without Stamp'}"
            )
            await context.bot.send_document(
                chat_id=chat_id,
                document=pdf_file,
                filename=fname,
                caption=caption,
                parse_mode="Markdown"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error generating invoice: {e}")


# ─── Main Bot Execution ───────────────────────────────────────────────────────
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_FROM_BOTFATHER":
        print("⚠️ Please set your TELEGRAM_BOT_TOKEN in telegram_bot.py or environment variables!")
        print("   Get a token from @BotFather on Telegram.")
        return

    print("🤖 Starting Telegram Bot 24/7 polling service...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    app.run_polling()


if __name__ == "__main__":
    main()
