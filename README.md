# ⚡ Energy Analytics Platform

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Zero_Trust-orange.svg)
![Security](https://img.shields.io/badge/Security-DevSecOps_Ready-red.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

An automated, highly secure web platform for energy data processing, field-routing generation, and debtor analytics. Built with a "Security-First" approach, featuring Zero Trust architecture, an integrated SOC (Security Operations Center) logging system, and advanced PDF parsing capabilities.

## 🛡️ Enterprise-Grade Security (DevSecOps)

This platform is hardened against common web vulnerabilities (OWASP Top 10) and operates completely cloaked from the public internet:

* **Zero Trust Architecture:** The application exposes **zero public ports**. All traffic is securely routed exclusively through a **Cloudflare Tunnel**, protected by strict WAF rules (Geo-blocking).
* **L7 Cloudflare Shield Integration:** Uses Cloudflare GraphQL API to monitor and block malicious traffic at the edge, logging edge-threats directly to the SOC.
* **Deep File Inspection:** Mitigation of malicious uploads using **Magic Bytes** (`libmagic1`) to verify actual MIME-type signatures, combined with deep XML-structure inspection inside `.zip/.xlsx` archives to prevent macro/malware execution.
* **PDF Redaction & Sanitization:** Implements physical data redaction (via `fitz.add_redact_annot`) during PDF splitting operations. This ensures no hidden text layers or ghost artifacts leak from original multi-page layouts into the final distributed files.
* **Constant-Time Cryptography:** Module access is protected using `secrets.compare_digest()` to completely eliminate Timing Attacks.
* **Ephemeral Data (Burn-after-reading):** Uploaded data is processed in isolated UUID-namespaces. Files are strictly **destroyed immediately post-download**. A background Garbage Collector acts as a failsafe, sweeping abandoned files every 30 minutes.
* **Integrated SOC Logging & Analytics:** Real-time threat monitoring records unauthorized access attempts and invalid file signatures to a local SQLite database. Triggers instant **Telegram Bot Alerts** (with tracked `CF-Connecting-IP` headers) and visualizes threat data via Matplotlib charts.
* **Hardened Docker Environment:** Containers execute entirely under a non-root user privilege model.

## 🚀 Core Business Logic Modules

* **Debts Analysis (Restricted):** Secure, password-protected processing of billing data. Automatically generates grouped financial reports with responsive column auto-sizing for LibreOffice/Excel compatibility.
* **Routes Generation:** Parses raw disconnect-warning datasets to automatically generate individual, formatted routing spreadsheets for field workers.
* **Calls Statistics:** Call center data parsing, dynamic aggregation, and cross-tabulation by employee and date.
* **PDF Smart Parsing & Distribution:** Advanced processing of 1C-generated PDF warning batches. The system dynamically calculates physical Y-coordinates to accurately split multi-page warnings. Extracts addresses using robust Regex and generates separated, sorted, and collated PDF files for individual field workers.

## 🌙 Smart UI/UX

* **Glassmorphism Design:** Modern, responsive interface using Bootstrap 5.
* **Adaptive Theme:** Built-in Dark/Light mode toggle with `localStorage` memory.
* **Interactive Kanban Board:** Custom chip-based UI for PDF routing. Assigning an address to one field worker dynamically disables and visually strikes-through the option for all others, ensuring zero duplicate assignments across massive datasets.
* **Live Security Dashboard:** Animated, real-time security threat and file-processing metrics displayed directly on the UI.
* **Smart States & Toasts:** Interactive Toast notifications for upload states. UI prevents duplicate downloads and alerts users when ephemeral files are safely purged from the server.

## 🛠️ Tech Stack

* **Backend:** Python 3.10, FastAPI, Uvicorn
* **Data Processing:** Pandas, OpenPyXL, PyMuPDF (fitz), Regex
* **Security & SOC:** Python-Magic, SQLite3, pyTelegramBotAPI, Matplotlib, Cloudflare GraphQL
* **Frontend:** HTML5, CSS3, Bootstrap 5, Jinja2 Templates, Vanilla JS
* **Infrastructure & Deployment:** Docker, Docker Compose, Cloudflare `cloudflared` daemon

## ⚙️ Quick Start (Docker Deployment)

**1. Clone the repository:**

    git clone https://github.com/RoninSoulKh/analytics_En.git
    cd analytics_En

**2. Create a `.env` file in the root directory with your secure credentials:**

    SECRET_ACCESS_KEY=your_secure_password_here
    TG_BOT_TOKEN=your_telegram_bot_token
    TG_CHAT_ID=your_telegram_chat_id
    TUNNEL_TOKEN=your_cloudflare_tunnel_token
    CF_ZONE_ID=your_cloudflare_zone_id
    CF_API_TOKEN=your_cloudflare_api_token

**3. Build and launch the containerized environment:**

    docker compose up -d --build

**4. Access and Routing:**
The application will be securely proxied through your configured Cloudflare Tunnel. Local direct access is disabled by design.

## 📊 Telegram SOC Bot Commands

* `/stats` - Generates a visual PNG chart of blocked security incidents logged in SQLite (1W, 1M, 1Y).
* `/log` - Fetches real-time L7 threat analytics from the Cloudflare GraphQL API.

## 📜 License
This project is officially licensed under the [MIT License](LICENSE).