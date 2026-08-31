# 🤖 Telegram Bot & Mini App Configuration Guide

> [!IMPORTANT]
> Keep your bot credentials secure. Never commit your `.env` file or private tokens to public repositories.

---

## 📋 **Bot Setup Reference**

| Parameter | Description / Example |
| --- | --- |
| **Bot Username** | `@your_bot_username` |
| **Direct Bot Link** | `https://t.me/your_bot_username` |
| **Direct Mini App Link** | `https://t.me/your_bot_username/app` |
| **Mini App Web URL** | `https://your-deployment-url.vercel.app` |

---

## 🔑 **Environment Setup (`.env`)**

Create a local `.env` file in the project root (this file is excluded by `.gitignore`):

```env
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_FROM_BOTFATHER
MINI_APP_URL=https://your-deployment-url.vercel.app
BOT_USERNAME=your_bot_username
```

---

## ⚡ **How to Run Telegram Bot**

To start the 24/7 Telegram Bot listener:

```bash
python telegram_bot.py
```
