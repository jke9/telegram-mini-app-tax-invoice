# 📚 JKE Telegram Mini App - Developer Guidelines

This document provides quick-reference guidelines, React hooks, TON blockchain connection examples, monetization frameworks, haptic templates, and Bot API 8.0+ / 9.0+ features to help you extend, test, and style your Telegram Mini App.

---

## 🚀 Getting Started

### 1. Launch the Local Development Server
Execute the lightweight Python development server from your terminal:
```bash
python server.py
```
*The app will be served locally at `http://localhost:8030`.*

### 2. Configure a Secure Tunnel (HTTPS)
Telegram requires all Mini Apps to be hosted on HTTPS. To test local changes on your phone:
1. Install ngrok (if not already installed).
2. Start an HTTP tunnel on port 8030:
   ```bash
   ngrok http 8030
   ```
3. Copy the secure forwarding link (e.g. `https://xxxx.ngrok-free.app`).

### 3. Register your App with BotFather
1. Message `@BotFather` on Telegram.
2. Run `/newapp` and select your bot.
3. Provide details (title, description, image).
4. When prompted for the **Web App URL**, paste your secure HTTPS tunnel link.
5. `@BotFather` will give you a direct link (e.g., `t.me/your_bot/app_name`).

---

## 🎨 Theme Styling Guide
Always style custom elements using the native Telegram CSS variables to support automatic dark/light mode switching:

```css
/* Card example using Telegram themes */
.my-card {
    background-color: var(--tg-theme-secondary-bg-color);
    color: var(--tg-theme-text-color);
    border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Button matching Telegram main action button */
.my-button {
    background-color: var(--tg-theme-button-color);
    color: var(--tg-theme-button-text-color);
}
```

---

## 📱 Useful SDK API Call Examples

### React Hook Wrapper (`useTelegram`)
```javascript
// hooks/useTelegram.js
import { useEffect, useState } from 'react';

export function useTelegram() {
    const tg = window.Telegram?.WebApp;
    
    return {
        tg,
        user: tg?.initDataUnsafe?.user,
        queryId: tg?.initDataUnsafe?.query_id,
        expand: () => tg?.expand(),
        close: () => tg?.close(),
        ready: () => tg?.ready(),
        theme: tg?.themeParams,
    };
}
```

### Trigger Haptic Feedback
```javascript
// Success vibration
window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');

// Impact tap
window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
```

### Display Native Alerts
```javascript
window.Telegram.WebApp.showAlert('Your changes have been saved to Odoo.');
```

### Display Native Dialogs
```javascript
window.Telegram.WebApp.showPopup({
    title: 'Delete Task',
    message: 'Are you sure you want to delete this task?',
    buttons: [
        {id: 'delete', type: 'destructive', text: 'Delete'},
        {id: 'cancel', type: 'cancel', text: 'Cancel'}
    ]
}, function(btnId) {
    if (btnId === 'delete') {
        // Execute deletion logic
    }
});
```

### Control the Bottom Buttons (Main & Secondary)
```javascript
// 1. Main Action Button
const mainBtn = window.Telegram.WebApp.MainButton;
mainBtn.setText("Confirm Actions");
mainBtn.show();
mainBtn.onClick(function() {
    // Actions executed when the main bottom button is clicked
});

// 2. Secondary Cancel Button (Bot API 7.10+)
const secBtn = window.Telegram.WebApp.SecondaryButton;
secBtn.setText("Cancel");
secBtn.show();
secBtn.onClick(function() {
    window.Telegram.WebApp.close();
});
```

---

## 🛠️ Advanced Bot API 8.0+ and 9.0+ Specifications

### Fullscreen and Safe Area Control
Mini Apps can launch and run in immersive full-screen:
```javascript
// Request Fullscreen
window.Telegram.WebApp.requestFullscreen();

// Check margins to avoid dynamic screen overlay cutouts
const topMargin = window.Telegram.WebApp.safeAreaInset.top;
const bottomMargin = window.Telegram.WebApp.safeAreaInset.bottom;
```

### Device Storage & Secure Storage API
Allows saving client-side options and keys persistently on the user's device:
```javascript
// 1. Standard Device Storage (Callback-based local database parameters)
window.Telegram.WebApp.DeviceStorage.setItem('key', 'value', function(err, success) {
    if (success) {
        window.Telegram.WebApp.DeviceStorage.getItem('key', function(err, val) {
            console.log("Returned:", val);
        });
    }
});

// 2. Secure Local Storage (Encrypted partition for access keys/auth tokens)
window.Telegram.WebApp.SecureStorage.setItem('auth_token', 'xxx', function(err, success) {
    if (success) {
        window.Telegram.WebApp.SecureStorage.getItem('auth_token', function(err, val) {
            console.log("Secure token returned:", val);
        });
    }
});
```

### Homescreen Shortcuts & Sharing Message
Prompt users to add a shortcut of the Mini App to their phone's home screen, and send custom inline share cards to any chat:
```javascript
// Add home screen shortcut
window.Telegram.WebApp.checkHomeScreenStatus(function(status) {
    if (status === 'missed') {
        window.Telegram.WebApp.addToHomeScreen();
    }
});

// Send share message sheet
window.Telegram.WebApp.shareMessage("Help us test the new JKE Odoo Manager!");
```

---

## 💎 Web3 (TON Blockchain) Connection
To connect TON cryptocurrency wallets inside the React Mini App:

```bash
npm install @tonconnect/ui-react
```

### Setup Provider
```jsx
import { TonConnectUIProvider, TonConnectButton } from '@tonconnect/ui-react';

function App() {
  return (
    <TonConnectUIProvider manifestUrl="https://your-app.com/tonconnect-manifest.json">
      <TonConnectButton />
    </TonConnectUIProvider>
  );
}
```

### Trigger TON Transaction
```jsx
import { useTonConnectUI } from '@tonconnect/ui-react';

function PaymentButton({ amount, recipientAddress }) {
  const [tonConnectUI] = useTonConnectUI();

  const handlePay = async () => {
    await tonConnectUI.sendTransaction({
      validUntil: Math.floor(Date.now() / 1000) + 60,
      messages: [{
        address: recipientAddress,
        amount: (amount * 1e9).toString(), // nanoTON conversion
      }]
    });
  };

  return <button onClick={handlePay}>Pay with TON Wallet</button>;
}
```

---

## 💰 In-App Payments (Telegram Stars)
To charge Telegram Stars for premium contents or Odoo reports:
```javascript
// Trigger Stars Invoice via Telegram Bot
bot.command('premium', (ctx) => {
  ctx.replyWithInvoice({
    title: 'Premium Upgrade',
    description: 'Unlock Advanced Odoo Visual Analytics',
    payload: 'premium_upgrade',
    provider_token: '', // Leave blank for Telegram Stars
    currency: 'XTR', // Stars currency code
    prices: [{ label: 'Premium', amount: 250 }], // 250 Stars
  });
});
```

---

## 📈 Referral & Sharing Systems
Add sharing widgets to generate organic users:
```javascript
function InviteButton({ userId }) {
  const referralLink = `https://t.me/your_bot?start=ref_${userId}`;
  
  const handleShare = () => {
    window.Telegram.WebApp.openTelegramLink(
      `https://t.me/share/url?url=${encodeURIComponent(referralLink)}&text=Join me on JKE Manager!`
    );
  };

  return <button onClick={handleShare}>Invite Friends</button>;
}
```

---

## 🔒 Backend Verification (Security)
To prevent users from spoofing their identities, the backend MUST validate the raw `initData` query string sent from the Telegram Mini App client.
Never trust `initDataUnsafe` for database operations or user authentication!

### Python Validation Snippet
```python
import hmac
import hashlib
from urllib.parse import parse_qsl

def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validates the data received from the Telegram Mini App client.
    Ref: https://core.telegram.org/bots/webapps#validating-data-received-from-the-mini-app
    """
    try:
        # Parse query parameters to dict
        parsed_data = dict(parse_qsl(init_data))
        hash_value = parsed_data.pop("hash", None)
        if not hash_value:
            return False
        
        # Construct data_check_string by sorting keys alphabetically
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        # Calculate secret key: HMAC-SHA256 of bot token with key "WebAppsData"
        secret_key = hmac.new(b"WebAppsData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        
        # Calculate hash of data_check_string using secret key
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(calculated_hash, hash_value)
    except Exception:
        return False
```

### Node.js Validation Snippet
```javascript
const crypto = require('crypto');

function validateTelegramInitData(initData, botToken) {
    const params = new URLSearchParams(initData);
    const hash = params.get('hash');
    params.delete('hash');

    // Sort parameters alphabetically and join them
    const dataCheckString = Array.from(params.entries())
        .map(([key, value]) => `${key}=${value}`)
        .sort()
        .join('\n');

    // Generate secret key
    const secretKey = crypto.createHmac('sha256', 'WebAppsData')
        .update(botToken)
        .digest();

    // Generate hash
    const calculatedHash = crypto.createHmac('sha256', secretKey)
        .update(dataCheckString)
        .digest('hex');

    return calculatedHash === hash;
}
```

---

## 🛠️ Recommended Libraries, UI Kits, and Boilerplates
Curated from the [Awesome Telegram Mini Apps](https://github.com/telegram-mini-apps-dev/awesome-telegram-mini-apps) repository:

### Core SDKs
* **[Official WebApp JS SDK](https://telegram.org/js/telegram-web-app.js)**: Native script loaded directly in `<head>`.
* **[@twa-dev/SDK](https://github.com/twa-dev/SDK)**: Main package wrapper for npm applications.
* **[@telegram-apps/sdk](https://github.com/Telegram-Web-Apps/twa.js)**: Modern, modular TypeScript SDK with reactive wrappers.

### UI Styling & Component Kits
* **[Telegram UI React Library](https://github.com/Telegram-Mini-Apps/TelegramUI)**: High-quality pre-designed elements replicating Telegram's native design system.
* **[@tonconnect/ui-react](https://github.com/ton-connect/sdk/tree/main/packages/ui)**: Seamless UI button and provider interface for TON Blockchain wallet connection.
* **[@twa-dev/Mark42](https://github.com/twa-dev/Mark42)**: An ultra-lightweight UI library optimized for fast load times.

### Init Data Validators
* **[telegram-webapp-auth (Python)](https://github.com/swimmwatch/telegram-webapp-auth)**: Python validation helper.
* **[init-data-golang (Go)](https://github.com/Telegram-Mini-Apps/init-data-golang)**: Performance-oriented signature validator for Go microservices.

### Boilerplates & Templates
* **[@twa-dev/vite-boilerplate](https://github.com/twa-dev/vite-boilerplate)**: Scaffolder for quick Vite + React setups.
* **[TON Integration Template](https://github.com/ton-community/twa-template)**: Template preconfigured with React, Vite, and TON Connect.
* **[Next.js Example](https://github.com/mauriciobraz/next.js-telegram-webapp)**: Template for full-stack Next.js applications.

