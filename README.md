# ⚡ Energy Analytics Platform

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![Cloudflare](https://img.shields.io/badge/Cloudflare-Zero_Trust-orange.svg)
![Security](https://img.shields.io/badge/Security-DevSecOps_Ready-red.svg)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF.svg?logo=github&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

An automated, highly secure web platform for energy data processing, field-routing generation, and debtor analytics. Built with a "Security-First" approach, featuring Zero Trust architecture, an integrated SOC (Security Operations Center) logging system, advanced PDF parsing capabilities, and a fully automated CI/CD pipeline.

## 🛡️ Enterprise-Grade Security (DevSecOps)

This platform is hardened against common web vulnerabilities (OWASP Top 10) and operates completely cloaked from the public internet:

* **Zero Trust Architecture:** The application exposes **zero public ports**. All traffic is securely routed exclusively through a **Cloudflare Tunnel**, protected by strict WAF rules (Geo-blocking).
* **L7 Cloudflare Shield Integration:** Uses Cloudflare GraphQL API to monitor and block malicious traffic at the edge, logging edge-threats directly to the SOC.
* **Deep File Inspection:** Mitigation of malicious uploads using **Magic Bytes** (`libmagic1`) to verify actual MIME-type signatures, combined with deep XML-structure inspection inside `.zip/.xlsx` archives to prevent macro/malware execution.
* **PDF Redaction & Sanitization:** Implements physical data redaction (via `fitz.add_redact_annot`) during PDF splitting operations. This ensures no hidden text layers or ghost artifacts leak from original multi-page layouts into the final distributed files.
* **Constant-Time Cryptography:** Module access is protected using `secrets.compare_digest()` to completely eliminate Timing Attacks.
* **Ephemeral Data (Burn-after-reading):** Uploaded data is processed in isolated UUID-namespaces. Files are strictly **destroyed immediately post-download**. A background Garbage Collector acts as a failsafe, sweeping abandoned files every 5 minutes.
* **Integrated SOC Logging & Analytics:** Real-time threat monitoring records unauthorized access attempts and invalid file signatures to a local SQLite database. Triggers instant **Telegram Bot Alerts** (with tracked `CF-Connecting-IP` headers) and visualizes threat data via Matplotlib charts.
* **Hardened Docker Environment:** Containers execute entirely under a non-root user privilege model.

## 🔄 Continuous Deployment (CI/CD)

The infrastructure utilizes a modern, hands-off deployment strategy designed to maintain the integrity of the Zero Trust network:

* **Automated Pipeline:** Pushing code to the `main` branch automatically triggers a GitHub Actions workflow.
* **Self-Hosted Runner:** Deployment commands are executed by a background daemon (`actions-runner`) residing *inside* the secure network. This entirely eliminates the need to expose SSH ports for remote deployments.
* **Secure Secrets Management:** Production environment variables (API Tokens, Keys) are securely injected into the `.env` file at runtime via GitHub Secrets, ensuring zero hardcoded credentials in the repository.
* **Zero-Downtime Builds:** The pipeline automatically pulls the latest commit, rebuilds the Docker image, and gracefully restarts the stack using `docker compose up -d --build --remove-orphans`.

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
* **Infrastructure:** Docker, Docker Compose, Cloudflare `cloudflared`
* **Automation:** GitHub Actions, Self-Hosted Runner

## ⚙️ Quick Start (Local Development)

**1. Clone the repository:**
```bash
git clone [https://github.com/RoninSoulKh/analytics_En.git](https://github.com/RoninSoulKh/analytics_En.git)
cd analytics_En
```

**2. Create a `.env` file with test credentials:**
```env
SECRET_ACCESS_KEY=local_test_password
TG_BOT_TOKEN=test_bot_token
TG_CHAT_ID=test_chat_id
# Tunnel tokens are not required for local dev without Cloudflare
```

**3. Build and launch the container:**
```bash
docker compose up -d --build
```

## 📊 Telegram SOC Bot Commands

* `/stats` - Generates a visual PNG chart of blocked security incidents logged in SQLite (1W, 1M, 1Y).
* `/log` - Fetches real-time L7 threat analytics from the Cloudflare GraphQL API.

## 📜 License
This project is officially licensed under the [MIT License](LICENSE).