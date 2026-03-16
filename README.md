# ⚡ Energy Analytics Platform

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Zero_Trust-orange.svg)
![Security](https://img.shields.io/badge/Security-DevSecOps_Ready-red.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

An automated, highly secure web platform for energy data processing, field-routing generation, and debtor analytics. Built with a "Security-First" approach, featuring Zero Trust architecture and an integrated SOC (Security Operations Center) logging system.

## 🛡️ Enterprise-Grade Security (DevSecOps)

This platform is hardened against common web vulnerabilities (OWASP Top 10) and operates completely cloaked from the public internet:

* **Zero Trust Architecture:** The application exposes **zero public ports**. All traffic is securely routed exclusively through a **Cloudflare Tunnel**, protected by strict WAF rules (Geo-blocking).
* **Deep File Inspection:** Mitigation of malicious uploads using **Magic Bytes** (`libmagic1`) to verify actual MIME-type signatures, not just file extensions.
* **Constant-Time Cryptography:** Module access is protected using `secrets.compare_digest()` to completely eliminate Timing Attacks.
* **Path Traversal Protection:** Strict sanitization of I/O operations using `os.path.basename` prevents directory traversal exploits.
* **Ephemeral Data Processing:** Uploaded data is processed in isolated UUID-namespaces. Files are instantly destroyed post-download, and a background Garbage Collector sweeps abandoned files every 30 minutes.
* **Integrated SOC Logging:** Real-time threat monitoring records unauthorized access attempts and invalid file signatures to a local SQLite database, triggering instant **Telegram Bot Alerts** with tracked `CF-Connecting-IP` headers.
* **Hardened Docker Environment:** Containers execute entirely under a non-root user privilege model.

## 🚀 Core Business Logic Modules

* **Debts Analysis (Restricted):** Secure, password-protected processing of billing data. Automatically generates grouped financial reports with responsive column auto-sizing for LibreOffice/Excel compatibility.
* **Routes Generation:** Parses raw disconnect-warning datasets to automatically generate individual, formatted routing spreadsheets for field workers.
* **Calls Statistics:** Call center data parsing, dynamic aggregation, and cross-tabulation by employee and date.

## 🌙 Smart UI/UX

* **Glassmorphism Design:** Modern, responsive interface using Bootstrap 5.
* **Adaptive Theme:** Built-in Dark/Light mode toggle with `localStorage` memory.
* **Smart Download States:** UI prevents duplicate downloads and alerts users when ephemeral files are safely purged from the server.

## 🛠️ Tech Stack

* **Backend:** Python 3.10, FastAPI, Uvicorn, Pandas, OpenPyXL, Python-Magic
* **Frontend:** HTML5, CSS3, Bootstrap 5, Jinja2 Templates
* **Infrastructure & Deployment:** Docker, Docker Compose, Cloudflare `cloudflared` daemon

## ⚙️ Quick Start (Docker Deployment)

**1. Clone the repository:**
```bash
git clone [https://github.com/RoninSoulKh/analytics_En.git](https://github.com/RoninSoulKh/analytics_En.git)
cd analytics_En
```

**2. Create a `.env` file in the root directory with your secure credentials:**
```env
SECRET_ACCESS_KEY=your_secure_password_here
TG_BOT_TOKEN=your_telegram_bot_token
TG_CHAT_ID=your_telegram_chat_id
TUNNEL_TOKEN=your_cloudflare_tunnel_token
```

**3. Build and launch the containerized environment:**
```bash
docker compose up -d --build
```

**4. Access and Routing:**
The application will be securely proxied through your configured Cloudflare Tunnel. Local direct access is disabled by design.

## 📜 License
This project is officially licensed under the [MIT License](LICENSE).