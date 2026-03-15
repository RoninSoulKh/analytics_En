# ⚡ Energy Analytics Platform

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![Security](https://img.shields.io/badge/Security-Zero_Trace-red.svg)

An automated, secure web platform for energy data processing and analytics. Built with a focus on data privacy, fast processing, and modern UI/UX.

## 🚀 Key Features

* **🛡️ Zero-Trace Security Architecture:** * Uploaded source files are instantly destroyed post-processing.
  * Generated reports auto-delete upon download.
  * Smart background garbage collector cleans up "forgotten" files every 30 minutes.
* **🌙 Smart UI/UX:** Built-in Dark/Light mode toggle with `localStorage` memory. Modern, responsive glass-morphism design.
* **📊 Business Logic Modules:**
  * **Debts Analysis:** Secure, password-protected processing of billing data.
  * **Routes Generation:** Automated routing list creation for field workers.
  * **Calls Statistics:** Call center data parsing and aggregation.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Uvicorn
* **Frontend:** HTML5, CSS3, Bootstrap 5, Jinja2 Templates
* **Infrastructure:** Docker, Docker Compose

## ⚙️ Quick Start (Docker)

1. Clone the repository:
   ```bash
   git clone [https://github.com/RoninSoulKh/analytics_En.git](https://github.com/RoninSoulKh/analytics_En.git)
   cd analytics_En
   ```

2. Create a `.env` file in the root directory and add your secure access key:
   ```env
   SECRET_ACCESS_KEY=your_secure_password_here
   ```

3. Build and run the container in the background:
   ```bash
   docker compose up -d --build
   ```

4. The application will be available at `http://localhost:8002`.

## 🔒 Security Notes
This project implements strict path traversal protections, file format validation, and UUID-based file isolation to prevent race conditions during concurrent user uploads.