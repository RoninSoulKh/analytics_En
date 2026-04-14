import pandas as pd
import requests
import json
import sqlite3
import re
import io
import time
from datetime import datetime

VISICOM_API_UK = "https://api.visicom.ua/data-api/5.0/uk/geocode.json"

def clean_address_for_api(street: str, house: str) -> str:
    if pd.isna(street) or str(street).strip() == "":
        return ""
    
    s = str(street).strip()
    s = re.sub(r'^[мг]\.\s*', '', s, flags=re.IGNORECASE)
    s = s.title()
    s = s.replace("В'їзд", "в'їзд").replace("Вул.", "вул.").replace("Пров.", "пров.")
    
    h = str(house).strip() if pd.notna(house) else ""
    h = re.sub(r'(?i)\b(д\.|д\s|буд\.|б\.)\s*', '', h)
    
    replacements = {
        'САЛТІВСЬКЕ': 'Салтівське шосе',
        'САЛТОВСКОЕ': 'Салтівське шосе',
        'ЮБІЛЕЙНИЙ': 'Ювілейний проспект',
        'ЮБИЛЕЙНЫЙ': 'Ювілейний проспект',
        'ГВ ШИРОНІНЦІВ': 'вулиця Гвардійців-Широнінців',
        'ТРАКТОРОВЕДОВ': 'проспект Тракторобудівників',
        'ТРАКТОРОБУДІВНИКІВ': 'проспект Тракторобудівників'
    }
    
    s_upper = str(street).strip().upper()
    for old, new in replacements.items():
        if old in s_upper:
            s = new
            break

    addr = f"{s}, {h}".strip(', ')
    return ' '.join(addr.split())

def fetch_polygon_from_visicom(clean_addr: str, api_key: str):
    variants = [f"Харків, {clean_addr}", clean_addr]
    
    for variant in variants:
        params = {"text": variant, "key": api_key, "limit": 1}
        try:
            resp = requests.get(VISICOM_API_UK, params=params, timeout=5)
            if resp.status_code != 200:
                print(f"\n[!] Помилка API: Код {resp.status_code}")
                time.sleep(1)
                continue
            
            data = resp.json()
            if data.get('type') == 'FeatureCollection' and data.get("features"):
                 feat = data["features"][0]
                 if "geometry" not in feat:
                     feat["geometry"] = feat.get("geo_centroid")
                 if feat.get("geometry"):
                     return json.dumps(feat)
                     
            elif data.get('type') == 'Feature':
                 if "geometry" not in data:
                     data["geometry"] = data.get("geo_centroid")
                 if data.get("geometry"):
                     return json.dumps(data)
                     
        except requests.exceptions.Timeout:
            time.sleep(1)
        except Exception:
            pass
        
        time.sleep(0.4) 
    return None

def get_or_fetch_geojson(full_addr: str, db_path: str, api_key: str):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT geojson FROM geocache WHERE raw_address = ?", (full_addr,))
        row = cursor.fetchone()
        if row: 
            return json.loads(row[0]) if row[0] else None
            
        print(f"🔍 API Запит: {full_addr}...", end=" ", flush=True)
        geojson_str = fetch_polygon_from_visicom(full_addr, api_key)
        print("✅ Знайдено" if geojson_str else "❌ Не знайдено")
            
        cursor.execute("INSERT INTO geocache (raw_address, clean_address, geojson) VALUES (?, ?, ?)",
                       (full_addr, full_addr, geojson_str))
        conn.commit()
        time.sleep(0.4) 
        return json.loads(geojson_str) if geojson_str else None

def parse_nedopuski_in_memory(file_bytes):
    if not file_bytes:
        return set()
        
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine='odf', header=None)
        nedopuski_addresses = set()
        current_date = datetime.now()
        
        for idx in range(1, len(df)):
            row = df.iloc[idx]
            street, house = row[0], row[1]
            date_val = row[8]
            
            if pd.isna(street) or pd.isna(date_val):
                continue
                
            try:
                n_date = pd.to_datetime(date_val, dayfirst=True)
                months_diff = (current_date.year - n_date.year) * 12 + current_date.month - n_date.month
                if months_diff < 2:
                    nedopuski_addresses.add(clean_address_for_api(street, house))
            except:
                pass
                
        return nedopuski_addresses
    except Exception as e:
        print(f"Помилка парсингу Недопусків: {e}")
        return set()

def process_map_file(file_path: str, db_path: str, api_key: str, nedopuski_bytes=None):
    df = pd.read_excel(file_path, sheet_name='2025', engine='odf', header=None)
    df[0] = df[0].replace(r'^\s*$', pd.NA, regex=True).ffill()
    
    recent_nedopuski = parse_nedopuski_in_memory(nedopuski_bytes)
    
    month_names = ['січ', 'лют', 'бер', 'квіт', 'трав', 'черв', 'лип', 'серп', 'вер', 'жовт', 'лист', 'груд']
    month_cols = []
    
    for i in range(2, len(df.columns)):
        words = str(df.iloc[0, i]).lower().split() + str(df.iloc[1, i]).lower().split()
        if any(word.startswith(m) for m in month_names for word in words):
            month_cols.append(i)

    # ЖОРСТКА ОБРІЗКА: Тільки 2 останні місяці! Ніяких жовтих точок і третіх місяців!
    cols_red = month_cols[-2:] if len(month_cols) >= 2 else month_cols

    features = []
    for idx in range(2, len(df)):
        row = df.iloc[idx]
        street, house = row[0], row[1]
        
        if pd.isna(house) or str(house).strip() == "":
            continue
        
        # Перевіряємо виключно останні 2 колонки (наприклад, Квітень, Березень)
        is_visited_red = any(pd.notna(row[c]) and str(row[c]).strip() != "" for c in cols_red)
        
        # Якщо в останніх 2 місяцях пусто — МИТТЄВО пропускаємо, API не чіпаємо!
        if not is_visited_red:
            continue

        clean_addr = clean_address_for_api(street, house)
        feature = get_or_fetch_geojson(clean_addr, db_path, api_key)
        
        if feature:
            feature['properties'] = {
                'address': clean_addr, 
                'color': "#dc3545", 
                'text_color': "#dc3545",
                'status': "Свіжий обхід",
                'has_nedopusk': clean_addr in recent_nedopuski,
                'is_active': True
            }
            features.append(feature)

    print(f"\n🏁 Готово! Будинків на карті: {len(features)}")
    return {"type": "FeatureCollection", "features": features}