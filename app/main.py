import os
import magic
import time
import shutil
import uuid
import asyncio
import secrets
import sqlite3
import zipfile
import io
import threading
from datetime import datetime
from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.scripts.tg_bot import send_telegram_alert, start_bot_polling
from app.scripts.debts import run_debts_analysis
from app.scripts.routes import run_routes_generation
from app.scripts.calls import run_calls_analysis

app = FastAPI(title="Energy Analytics API")

# Security configuration
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY", "change_me_in_production")
UPLOAD_DIR = "uploads"
DOWNLOAD_DIR = "downloads"
DB_FILE = "security_logs.db"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Database Setup ---

def init_db():
    """Initialize SQLite database for SOC logging."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event TEXT,
                ip TEXT,
                country TEXT,
                details TEXT
            )
        ''')
init_db()
threading.Thread(target=start_bot_polling, daemon=True).start()

# --- Utility Functions ---

def log_to_db(event: str, ip: str, country: str, details: str = ""):
    """Write security events to SQLite database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO logs (timestamp, event, ip, country, details) VALUES (?, ?, ?, ?, ?)",
                (timestamp, event, ip, country, details)
            )
    except Exception as e:
        print(f"DB Write Error: {e}")

def get_client_info(request: Request):
    """Extract real client IP and country via Cloudflare headers."""
    ip = request.headers.get("CF-Connecting-IP") or request.client.host
    country = request.headers.get("CF-IPCountry") or "Unknown"
    return ip, country

def remove_file(path: str):
    """Safely remove a file from the filesystem."""
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Cleanup error: {path} - {e}")

async def auto_delete_task(path: str, delay: int = 1800):
    """Background task to delete files after a specific retention period."""
    await asyncio.sleep(delay)
    remove_file(path)

def maintenance_cleanup():
    """Clear temporary files older than 30 minutes."""
    now = time.time()
    for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if os.path.getmtime(p) < now - 1800:
                remove_file(p)

def is_valid_spreadsheet_archive(file_content: bytes) -> bool:
    """Deep inspection of ZIP archives to verify spreadsheet structures."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as z:
            file_list = z.namelist()
            is_xlsx = "[Content_Types].xml" in file_list or "xl/workbook.xml" in file_list
            is_ods = "mimetype" in file_list and "content.xml" in file_list
            return is_xlsx or is_ods
    except Exception:
        return False

# --- Routes ---

@app.post("/verify-password")
async def verify_password(request: Request, background_tasks: BackgroundTasks, access_password: str = Form(...)):
    # Constant-time comparison to prevent timing attacks
    if secrets.compare_digest(access_password, SECRET_ACCESS_KEY):
        return {"status": "authorized"}
    
    # Log brute-force attempts on the API endpoint
    client_ip, client_country = get_client_info(request)
    details = "ACTION: WRONG_PASSWORD_API"
    
    log_entry = f"EVENT: UNAUTHORIZED_ACCESS_ATTEMPT\nSRC_IP: {client_ip}\nREGION: {client_country}\n{details}"
    
    background_tasks.add_task(send_telegram_alert, log_entry)
    background_tasks.add_task(log_to_db, "UNAUTHORIZED_ACCESS_ATTEMPT", client_ip, client_country, details)
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/downloads/{filename}")
async def secure_download(filename: str, background_tasks: BackgroundTasks):
    # Prevent Directory Traversal attacks
    safe_name = os.path.basename(filename)
    path = os.path.join(DOWNLOAD_DIR, safe_name)
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File expired or not found")
    
    # One-time download: trigger deletion after serving
    background_tasks.add_task(remove_file, path)
    return FileResponse(path=path, filename=safe_name)

@app.post("/upload")
async def handle_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    report_type: str = Form(...),
    access_password: str = Form(None)
):
    background_tasks.add_task(maintenance_cleanup)
    
    original_name = os.path.basename(file.filename)
    uid = str(uuid.uuid4())[:8]
    storage_name = f"{uid}_{original_name}"
    temp_path = os.path.join(UPLOAD_DIR, storage_name)

    # MIME type verification using Magic Bytes
    header = await file.read(2048)
    await file.seek(0)
    detected_mime = magic.from_buffer(header, mime=True)
    
    allowed_mimes = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/csv',
        'application/csv',
        'application/octet-stream',
        'application/zip',
        'application/vnd.oasis.opendocument.spreadsheet',
        'application/pdf'
    ]
    
    allowed_extensions = ('.xlsx', '.xls', '.csv', '.ods', '.pdf')
    
    # 1. Basic Validation
    if not original_name.lower().endswith(allowed_extensions) or detected_mime not in allowed_mimes:
        client_ip, client_country = get_client_info(request)
        details = f"FILE: {original_name} | MIME: {detected_mime}"
        
        log_entry = f"EVENT: UNAUTHORIZED_FILE_UPLOAD\nSRC_IP: {client_ip}\nREGION: {client_country}\n{details}"
        
        background_tasks.add_task(send_telegram_alert, log_entry)
        background_tasks.add_task(log_to_db, "UNAUTHORIZED_FILE_UPLOAD", client_ip, client_country, details)
        
        return templates.TemplateResponse("result.html", {
            "request": request,
            "error": "SECURITY_VIOLATION: Invalid file signature. Incident logged."
        })

    # 2. Deep Inspection for Archives
    if detected_mime in ['application/zip', 'application/octet-stream']:
        full_content = await file.read()
        await file.seek(0)
        
        if not is_valid_spreadsheet_archive(full_content):
            client_ip, client_country = get_client_info(request)
            details = f"FILE: {original_name} | REASON: Malformed archive payload"
            
            log_entry = f"EVENT: MALICIOUS_PAYLOAD_BLOCKED\nSRC_IP: {client_ip}\nREGION: {client_country}\n{details}"
            
            background_tasks.add_task(send_telegram_alert, log_entry)
            background_tasks.add_task(log_to_db, "MALICIOUS_PAYLOAD_BLOCKED", client_ip, client_country, details)
            
            return templates.TemplateResponse("result.html", {
                "request": request,
                "error": "SECURITY_VIOLATION: Invalid payload structure. Incident logged."
            })

    # Access control for restricted modules
    if report_type == "debts":
        if not access_password or not secrets.compare_digest(access_password, SECRET_ACCESS_KEY):
            client_ip, client_country = get_client_info(request)
            details = "ACTION: WRONG_PASSWORD_FORM"
            
            log_entry = f"EVENT: BRUTEFORCE_ATTEMPT_DEBTS\nSRC_IP: {client_ip}\nREGION: {client_country}\n{details}"
            
            background_tasks.add_task(send_telegram_alert, log_entry)
            background_tasks.add_task(log_to_db, "BRUTEFORCE_ATTEMPT_DEBTS", client_ip, client_country, details)

            return templates.TemplateResponse("result.html", {
                "request": request,
                "error": "ACCESS_DENIED: Critical module restricted. Incident logged."
            })
            
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        files_list = []
        out_name = None

        if report_type == "debts":
            out_name = run_debts_analysis(temp_path, DOWNLOAD_DIR)
        elif report_type == "routes":
            files_list = run_routes_generation(temp_path, DOWNLOAD_DIR)
        elif report_type == "calls":
            out_name = run_calls_analysis(temp_path, DOWNLOAD_DIR)

        if out_name:
            background_tasks.add_task(auto_delete_task, os.path.join(DOWNLOAD_DIR, out_name))
        for f in files_list:
            background_tasks.add_task(auto_delete_task, os.path.join(DOWNLOAD_DIR, f["filename"]))

        return templates.TemplateResponse("result.html", {
            "request": request,
            "filename": out_name,
            "files_list": files_list,
            "download_url": f"/downloads/{out_name}" if out_name else None
        })
        
    except Exception as e:
        print(f"Processing error: {e}")
        return templates.TemplateResponse("result.html", {
            "request": request,
            "error": "An error occurred during report generation."
        })
    finally:
        remove_file(temp_path)