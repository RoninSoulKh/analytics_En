from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks, Form, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import time
import shutil
import uuid
import asyncio

# Імпорт твоїх скриптів
from app.scripts.debts import run_debts_analysis
from app.scripts.routes import run_routes_generation
from app.scripts.calls import run_calls_analysis

app = FastAPI(title="Energy Analytics")

# ПАРОЛЬ ЖИВЕ ТІЛЬКИ ТУТ
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY", "default_secure_password")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
DOWNLOAD_DIR = "downloads"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- БЛОК БЕЗПЕКИ ТА ЗНИЩЕННЯ ДАНИХ ---

def remove_single_file(path: str):
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Не зміг видалити файл {path}: {str(e)}")

# НОВЕ: Функція індивідуального таймера
async def delete_after_delay(file_path: str, delay_seconds: int = 1800):
    await asyncio.sleep(delay_seconds)
    remove_single_file(file_path)

def cleanup_old_files():
    current_time = time.time()
    for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.getmtime(file_path) < current_time - 1800:
                    if os.path.isfile(file_path):
                        remove_single_file(file_path)

# --- РОУТИ ---

@app.post("/verify-password")
async def verify_password(access_password: str = Form(...)):
    if access_password == SECRET_ACCESS_KEY:
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Wrong password")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Аналітика Енергозбут"})

@app.get("/downloads/{filename}")
async def secure_download(filename: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл вже видалено з міркувань безпеки. Завантажте звіт наново.")
    
    background_tasks.add_task(remove_single_file, file_path)
    return FileResponse(path=file_path, filename=filename)

@app.post("/upload")
async def handle_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    report_type: str = Form(...),
    access_password: str = Form(None)
):
    background_tasks.add_task(cleanup_old_files)
    
    safe_filename = os.path.basename(file.filename)
    unique_id = str(uuid.uuid4())[:6] 
    secure_filename = f"{unique_id}_{safe_filename}"
    input_path = os.path.join(UPLOAD_DIR, secure_filename)

    if not safe_filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        return templates.TemplateResponse("result.html", {
            "request": request,
            "error": "Система безпеки: Дозволені лише формати Excel або CSV!"
        })

    if report_type == "debts":
        if access_password != SECRET_ACCESS_KEY:
            return templates.TemplateResponse("result.html", {
                "request": request,
                "error": "Доступ заборонено! Невірний пароль для розділу заборгованості."
            })
            
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        files_list = [] 
        output_filename = None 

        if report_type == "debts":
            output_filename = run_debts_analysis(input_path, DOWNLOAD_DIR)
        elif report_type == "routes":
            files_list = run_routes_generation(input_path, DOWNLOAD_DIR)
        elif report_type == "calls":
            output_filename = run_calls_analysis(input_path, DOWNLOAD_DIR)
        else:
            output_filename = secure_filename
            shutil.copy(input_path, os.path.join(DOWNLOAD_DIR, output_filename))

        # --- НОВЕ: Заводимо таймери на згенеровані файли ---
        if output_filename:
            report_path = os.path.join(DOWNLOAD_DIR, output_filename)
            background_tasks.add_task(delete_after_delay, report_path, 1800)
            
        if files_list:
            for f in files_list:
                report_path = os.path.join(DOWNLOAD_DIR, f["filename"])
                background_tasks.add_task(delete_after_delay, report_path, 1800)
        # ---------------------------------------------------

        return templates.TemplateResponse("result.html", {
            "request": request,
            "filename": output_filename,
            "files_list": files_list,
            "download_url": f"/downloads/{output_filename}" if output_filename else None
        })
        
    except Exception as e:
        print(f"ПОМИЛКА ОБРОБКИ: {str(e)}") 
        return templates.TemplateResponse("result.html", {
            "request": request,
            "error": "Сталася системна помилка при обробці файлу. Перевірте структуру таблиці або зверніться до адміністратора."
        })
    finally:
        remove_single_file(input_path)