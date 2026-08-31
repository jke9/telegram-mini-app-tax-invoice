# 🌐 24/7 Online Deployment Guide — Telegram Mini App & Bot

This guide explains how to host your **Tax Invoice Generator Telegram Mini App & Bot 24/7 online** for free or low cost, so it works anytime on your mobile phone without keeping your computer turned on.

---

## 📋 Prerequisites
1. **Telegram Bot Token**: Message `@BotFather` on Telegram:
   - Run `/newbot` → Name it `Tax Invoice Generator Bot`.
   - Copy your **API Token** (e.g. `7812345678:AAH...`).
2. **GitHub Account**: To host code for free deployment.

---

## ⚡ Option A: Free 24/7 Cloud Hosting (Render.com / Railway.app) — Recommended

### Step 1: Push Project to GitHub
Push this repository folder (`Bulk Invoice`) to your personal GitHub account.

### Step 2: Deploy to Render.com (Free)
1. Go to [Render.com](https://render.com) and create a free account.
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository.
4. Set details:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python Telegram_Mini_App/api_server.py`
5. Add Environment Variables:
   - `TELEGRAM_BOT_TOKEN` = `your_token_from_botfather`
6. Click **Deploy Web Service**.
7. Render will provide a free HTTPS URL: e.g. `https://tax-invoice-app.onrender.com`.

### Step 3: Link Mini App in @BotFather
1. Open Telegram and message `@BotFather`.
2. Run `/newapp` → Select your bot.
3. Title: `Tax Invoice Generator`
4. When prompted for **Web App URL**, paste your secure Render HTTPS link:
   `https://tax-invoice-app.onrender.com`
5. `@BotFather` will give you a direct 24/7 link: `t.me/your_bot_name/app`!

---

## 🏠 Option B: Fast 24/7 Testing from your PC with Ngrok (Temporary Tunnel)

If you want to test on your mobile phone right now while your PC is on:

1. Launch servers:
   ```bash
   c:\Users\Divine\Desktop\Bulk Invoice\Telegram_Mini_App\start.bat
   ```
2. Start free ngrok HTTPS tunnel for port 8030:
   ```bash
   ngrok http 8030
   ```
3. Copy the `https://xxxx.ngrok-free.app` URL and paste it into `@BotFather` as your Web App URL.
4. Open Telegram on your phone and tap the Mini App button — it will open live on your phone!

---

## 📄 Summary of Telegram Bot Commands & Files

- 📄 **Bot Script**: [telegram_bot.py](file:///c:/Users/Divine/Desktop/Bulk%20Invoice/Telegram_Mini_App/telegram_bot.py) — 24/7 Bot polling script that sends PDFs directly into your chat.
- ⚡ **API Server**: [api_server.py](file:///c:/Users/Divine/Desktop/Bulk%20Invoice/Telegram_Mini_App/api_server.py) — Flask backend on Port 8031.
- 📱 **Mini App UI**: [index.html](file:///c:/Users/Divine/Desktop/Bulk%20Invoice/Telegram_Mini_App/index.html) — 5-step wizard UI.
