# 🧾 JKE Tax & Proforma Invoice Generator

A production-grade **Telegram Mini App & Web Invoice Generator** designed to create GST-compliant **Tax Invoices** and **Proforma Invoices** with Indian numbering formats (`1,00,000.00`), bi-directional tax calculations (Taxable ↔ Grand Total), whole-number auto round-off, company stamps, and 24/7 Telegram Bot delivery.

---

## 🌟 Key Features

- **Dynamic Invoice Switcher**: Seamlessly toggle between **Tax Invoice** and **Proforma Invoice** with a glassmorphic header dropdown selector.
- **Bi-Directional Tax Calculation**: Enter either the **Taxable Amount** or target **Grand Total** — the engine computes CGST (9%), SGST (9%), and automatic whole-number rounding.
- **Master Data Manager**: Manage Contractors, Customers, Bank Accounts, and Work Descriptions with search and on-the-fly additions.
- **Vector PDF Engine**: ReportLab vector PDF generator matching standard government & commercial tax invoice formats.
- **Telegram Integration**: Runs as a Telegram Mini App with native haptic feedback, theme synchronization, passcode lock (`0101`), and automatic PDF delivery to user chats.
- **Deploy Anywhere**: Works locally with lightweight Python servers or globally via Vercel serverless deployment.

---

## 📁 Repository Structure

```
.
├── index.html                        # Telegram Mini App Frontend Entrypoint
├── app.css                           # Modern Glassmorphic Styles & Animations
├── app.js                            # Frontend Logic, State & Telegram SDK Handler
│
├── api_server.py                     # Flask API Server (Port 8031)
├── server.py                         # Static HTTP Frontend Server (Port 8030)
├── telegram_bot.py                   # Telegram Bot (24/7 Polling & PDF Delivery)
├── generate_from_form.py             # Auto-lookup Invoice Generation Service
├── generate_tax_invoice_from_excel.py# Core ReportLab Vector PDF Engine
├── master_details_manager.py         # Master Registry Query Helper
│
├── master_invoice_details.json       # Master Database (Contractors, Customers, Projects)
├── .env.example                      # Environment Variables Template
├── requirements.txt                  # Python Dependencies
├── vercel.json                       # Vercel Deployment Configuration
├── start.bat                         # Windows One-Click Dev Server Launcher
│
├── Stamps/                           # Official Company Stamp & Signature Images
├── assets/                           # App Previews & Bot Screenshots
├── docs/                             # Developer Documentation & Setup Guides
│   ├── DEPLOYMENT_GUIDE.md           # 24/7 Cloud Deployment Guide
│   ├── GUIDELINES.md                 # Telegram Mini App SDK & Web3 Specifications
│   └── TELEGRAM_BOT_CREDENTIALS.md   # Bot Tokens & Links Reference
└── outputs/                          # Generated Invoice PDFs (Gitignored)
```

---

## 🚀 Quick Start (Local Development)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Servers
Run the batch launcher (Windows):
```cmd
start.bat
```
Or start the servers manually:
```bash
# Terminal 1: Backend API (Port 8031)
python api_server.py

# Terminal 2: Frontend Web Server (Port 8030)
python server.py

# Terminal 3: Telegram Bot (Optional)
python telegram_bot.py
```

- **Mini App Frontend**: [http://localhost:8030](http://localhost:8030)
- **API Health Check**: [http://localhost:8031/api/health](http://localhost:8031/api/health)

---

## ⚙️ CLI Invoice Generation

Generate invoices directly from the terminal:

```bash
# Tax Invoice
python generate_from_form.py --doc-type tax_invoice --amount 500000 --output outputs/tax_invoice.pdf

# Proforma Invoice
python generate_from_form.py --doc-type proforma_invoice --amount 500000 --output outputs/proforma_invoice.pdf
```

---

## 📚 Documentation

For advanced deployment instructions, API details, and Bot setup:
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Telegram Developer Guidelines](docs/GUIDELINES.md)
- [Bot Credentials & Setup](docs/TELEGRAM_BOT_CREDENTIALS.md)
