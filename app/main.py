import os
import magic
import time
import shutil
import uuid
import json
import asyncio
import secrets
import sqlite3
import zipfile
import io
import threading
from datetime import datetime
from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.scripts.map_generator import process_map_file
from dotenv import load_dotenv

from app.scripts.tg_bot import send_telegram_alert, start_bot_polling
from app.scripts.debts import run_debts_analysis
from app.scripts.routes import run_routes_generation
from app.scripts.calls import run_calls_analysis
from app.scripts.warnings import run_warnings_analysis
from app.scripts.pdf_processor import PDFProcessor 

load_dotenv()

app = FastAPI(title="Energy Analytics API")

# Security configuration
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY", "change_me_in_production")
UPLOAD_DIR = "uploads"
DOWNLOAD_DIR = "downloads"
DB_FILE = "security_logs.db"
PDF_TEMP_DIR = os.path.join("temp", "pdf_processing") 

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(PDF_TEMP_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Database Setup ---

def init_db():
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
        # НОВОЕ: Добавляем таблицу для кэширования полигонов Visicom
        conn.execute('''
            CREATE TABLE IF NOT EXISTS geocache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_address TEXT UNIQUE,
                clean_address TEXT,
                geojson TEXT
            )
        ''')
init_db()
threading.Thread(target=start_bot_polling, daemon=True).start()

def periodic_cleanup():
    while True:
        time.sleep(300) # Проверяем каждые 5 минут
        maintenance_cleanup()

threading.Thread(target=periodic_cleanup, daemon=True).start()

# --- Utility Functions ---

def log_to_db(event: str, ip: str, country: str, details: str = ""):
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
    ip = request.headers.get("CF-Connecting-IP") or request.client.host
    country = request.headers.get("CF-IPCountry") or "Unknown"
    return ip, country

def remove_file(path: str):
    if os.path.exists(path):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"Cleanup error: {path} - {e}")

async def auto_delete_task(path: str, delay: int = 1800):
    await asyncio.sleep(delay)
    remove_file(path)

def maintenance_cleanup():
    now = time.time()
    for folder in [UPLOAD_DIR, DOWNLOAD_DIR, PDF_TEMP_DIR]:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if os.path.getmtime(p) < now - 300:
                remove_file(p)

def is_valid_spreadsheet_archive(file_content: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as z:
            file_list = z.namelist()
            is_xlsx = "[Content_Types].xml" in file_list or "xl/workbook.xml" in file_list
            is_ods = "mimetype" in file_list and "content.xml" in file_list
            return is_xlsx or is_ods
    except Exception:
        return False

# --- Core Routes ---

@app.post("/verify-password")
async def verify_password(request: Request, background_tasks: BackgroundTasks, access_password: str = Form(...)):
    if secrets.compare_digest(access_password, SECRET_ACCESS_KEY):
        return {"status": "authorized"}
    
    client_ip, client_country = get_client_info(request)
    details = "ACTION: WRONG_PASSWORD_API"
    log_entry = f"EVENT: UNAUTHORIZED_ACCESS_ATTEMPT\nSRC_IP: {client_ip}\nREGION: {client_country}\n{details}"
    
    background_tasks.add_task(send_telegram_alert, log_entry)
    background_tasks.add_task(log_to_db, "UNAUTHORIZED_ACCESS_ATTEMPT", client_ip, client_country, details)
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/downloads/{filename}")
async def secure_download(filename: str, background_tasks: BackgroundTasks):
    safe_name = os.path.basename(filename)
    path = os.path.join(DOWNLOAD_DIR, safe_name)
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File expired or not found")
    
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
    
    client_ip, client_country = get_client_info(request)
    original_name = os.path.basename(file.filename)
    uid = str(uuid.uuid4())[:8]
    storage_name = f"{uid}_{original_name}"
    temp_path = os.path.join(UPLOAD_DIR, storage_name)

    header = await file.read(2048)
    await file.seek(0)
    detected_mime = magic.from_buffer(header, mime=True)
    
    allowed_mimes = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel', 'text/csv', 'application/csv',
        'application/octet-stream', 'application/zip',
        'application/vnd.oasis.opendocument.spreadsheet', 'application/pdf'
    ]
    allowed_extensions = ('.xlsx', '.xls', '.csv', '.ods', '.pdf')
    
    if not original_name.lower().endswith(allowed_extensions) or detected_mime not in allowed_mimes:
        return templates.TemplateResponse(request=request, name="result.html", context={
            "request": request, "error": "SECURITY_VIOLATION: Invalid file signature."
        })

    if report_type == "debts":
        if not access_password or not secrets.compare_digest(access_password, SECRET_ACCESS_KEY):
            return templates.TemplateResponse(request=request, name="result.html", context={
                "request": request, "error": "ACCESS_DENIED: Critical module restricted."
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
        elif report_type == "warnings":
            out_name = run_warnings_analysis(temp_path, DOWNLOAD_DIR)

        if out_name:
            background_tasks.add_task(auto_delete_task, os.path.join(DOWNLOAD_DIR, out_name))
        for f in files_list:
            background_tasks.add_task(auto_delete_task, os.path.join(DOWNLOAD_DIR, f["filename"]))

        log_details = f"FILE: {original_name} | TYPE: {report_type}"
        log_to_db("FILE_UPLOAD", client_ip, client_country, log_details)

        return templates.TemplateResponse(request=request, name="result.html", context={
            "request": request,
            "filename": out_name,
            "files_list": files_list,
            "download_url": f"/downloads/{out_name}" if out_name else None
        })
        
    except Exception as e:
        print(f"Processing error: {e}")
        return templates.TemplateResponse(request=request, name="result.html", context={
            "request": request, "error": "Processing Error"
        })
    finally:
        remove_file(temp_path)

# --- PDF Tools Routes ---

@app.get("/pdf", response_class=HTMLResponse)
async def pdf_page(request: Request):
    return templates.TemplateResponse(request=request, name="pdf.html", context={"request": request})

@app.post("/api/pdf/upload-and-parse")
async def upload_and_parse_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    method: str = Form(...), 
    workers: int = Form(1)
):
    background_tasks.add_task(maintenance_cleanup)
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    session_id = str(uuid.uuid4())
    session_dir = os.path.join(PDF_TEMP_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    file_path = os.path.join(session_dir, "original.pdf")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        processor = PDFProcessor(file_path)
        cards_data = processor.parse_and_split()
        
        with open(os.path.join(session_dir, "cards_data.json"), "w", encoding="utf-8") as f:
            json.dump(cards_data, f, ensure_ascii=False)

        if method == "order":
            sorted_cards = processor.sort_cards_by_address(cards_data)
            output_file = os.path.join(session_dir, "sorted_output.pdf")
            processor.merge_cards_to_pdf(sorted_cards, output_file)
            return JSONResponse(content={
                "status": "success", 
                "download_url": f"/api/pdf/download/{session_id}/sorted_output.pdf",
                "message": "Файл успішно відсортовано"
            })
            
        elif method == "workers":
            grouped_addresses = processor.group_by_street_and_house(cards_data)
            return JSONResponse(content={
                "status": "success",
                "session_id": session_id,
                "addresses": grouped_addresses,
                "workers": workers
            })

    except Exception as e:
        shutil.rmtree(session_dir, ignore_errors=True)
        print(f"Error processing PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pdf/generate-workers")
async def generate_workers_pdf(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    distribution = data.get("distribution")
    session_dir = os.path.join(PDF_TEMP_DIR, session_id)

    if not os.path.exists(session_dir):
        raise HTTPException(status_code=404, detail="Session not found or expired")

    try:
        with open(os.path.join(session_dir, "cards_data.json"), "r", encoding="utf-8") as f:
            cards_data = json.load(f)
            
        processor = PDFProcessor(os.path.join(session_dir, "original.pdf"))
        output_files = []
        for worker_id, assigned_houses in distribution.items():
            if not assigned_houses: continue
            
            worker_cards = processor.filter_cards_by_houses(cards_data, assigned_houses)
            sorted_worker_cards = processor.sort_cards_by_address(worker_cards)
            
            output_filename = f"Вимога_повідомлення_{worker_id}.pdf"
            output_path = os.path.join(session_dir, output_filename)
            
            processor.merge_cards_to_pdf(sorted_worker_cards, output_path)
            output_files.append({"worker": worker_id, "url": f"/api/pdf/download/{session_id}/{output_filename}"})

        return JSONResponse(content={"status": "success", "files": output_files})

    except Exception as e:
        print(f"Error generating worker PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pdf/download/{session_id}/{filename}")
async def download_pdf(session_id: str, filename: str):
    file_path = os.path.join(PDF_TEMP_DIR, session_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(path=file_path, filename=filename, media_type='application/pdf')

@app.post("/api/map/generate")
async def map_generate(
    request: Request, 
    master_file: UploadFile = File(...),
    nedopuski_file: UploadFile = File(None)
):
    api_key = os.getenv("VISICOM_DATA_KEY")
    if not api_key:
        return JSONResponse({"error": "Ключ VISICOM_DATA_KEY не налаштовано на сервері!"}, status_code=500)
        
    temp_path = os.path.join(UPLOAD_DIR, master_file.filename)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(master_file.file, buffer)
        
    nedopuski_bytes = None
    if nedopuski_file:
        nedopuski_bytes = await nedopuski_file.read()
        
    try:
        geojson_data = process_map_file(temp_path, DB_FILE, api_key, nedopuski_bytes)
        return JSONResponse(geojson_data)
    except Exception as e:
        print(f"Map processing error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        remove_file(temp_path)

@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    tiles_key = os.getenv("VISICOM_TILES_KEY", "")
    return templates.TemplateResponse(request=request, name="map.html", context={"request": request, "visicom_tiles_key": tiles_key})