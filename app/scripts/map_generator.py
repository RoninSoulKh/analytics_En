import pandas as pd
import requests
import json
import sqlite3
import re
import os

VISICOM_API_UK = "https://api.visicom.ua/data-api/5.0/uk/search.json"
VISICOM_API_RU = "https://api.visicom.ua/data-api/5.0/ru/search.json"

def clean_address_for_api(street: str, house: str) -> str:
    """Улучшенный очиститель: понимает шосе, проспекты и лечит Салтовку"""
    if pd.isna(street) or str(street).strip() == "": return ""
    
    s = str(street).strip().upper()
    h = str(house).strip() if pd.notna(house) else ""
    h = re.sub(r'(?i)\b(д\.|д\s|буд\.|б\.)\s*', '', h)
    
    # --- БЛОК ИСКЛЮЧЕНИЙ (самая дичь из таблиц) ---
    replacements = {
        'САЛТІВСЬКЕ': 'Салтівське шосе',
        'САЛТОВСКОЕ': 'Салтівське шосе',
        'ЮБІЛЕЙНИЙ': 'Ювілейний проспект',
        'ЮБИЛЕЙНЫЙ': 'Ювілейний проспект',
        'ГВ ШИРОНІНЦІВ': 'Гвардійців-Широнінців вулиця',
        'ГВ ШИРОНИНЦЕВ': 'Гвардійців-Широнінців вулиця',
        'ТРАКТОРОВЕДОВ': 'Тракторобудівників проспект',
        'ТРАКТОРОБУДІВНИКІВ': 'Тракторобудівників проспект'
    }
    
    for old, new in replacements.items():
        if old in s:
            s = new
            break

    # --- ОПРЕДЕЛЕНИЕ ТИПА (вул, пров, шосе) ---
    # Если в названии УЖЕ есть тип (ШОСЕ, ПРОСПЕКТ и т.д.), мы ничего не добавляем
    known_types = ['ШОСЕ', 'ПРОСП', 'ПРОВ', 'ВУЛ', 'МАЙДАН', 'В\'ЇЗД', 'В-Д', 'ПЕР']
    has_type = any(t in s for t in known_types)
    
    if not has_type:
        # Если типа нет, пробуем почистить русские сокращения
        s = s.replace('УЛ ', 'вул. ').replace('ПЕР ', 'пров. ').replace('ВЪЕЗД ', "в'їзд ")
        # Если всё еще нет типа - по умолчанию это улица
        if not any(t in s.upper() for t in ['ВУЛ.', 'ПРОВ.', 'ПРОСП.', "В'ЇЗД"]):
            s = f"вул. {s}"

    # Финальная сборка
    addr = f"{s}, {h}".strip(', ')
    addr = ' '.join(addr.split())
    
    return f"м. Харків, {addr}"

def fetch_polygon_from_visicom(clean_addr: str, api_key: str):
    """Пробует найти адрес. Сначала УКР, потом РУС, потом 'как есть'"""
    params = {"text": clean_addr, "key": api_key, "limit": 1}
    
    # 1. Сначала пробуем наш 'умный' адрес на УКР и РУС
    for url in [VISICOM_API_UK, VISICOM_API_RU]:
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("features"):
                    feat = data["features"][0]
                    if "geometry" not in feat:
                        feat["geometry"] = feat.get("geo_centroid")
                    return json.dumps(feat)
        except: continue
        
    # 2. Если не вышло - пробуем БЕЗ города (иногда API так лучше понимает)
    short_addr = clean_addr.replace("м. Харків, ", "")
    try:
        resp = requests.get(VISICOM_API_UK, params={"text": short_addr, "key": api_key, "limit": 1}, timeout=10)
        if resp.status_code == 200 and resp.json().get("features"):
            feat = resp.json()["features"][0]
            if "geometry" not in feat: feat["geometry"] = feat.get("geo_centroid")
            return json.dumps(feat)
    except: pass
    
    return None

def get_or_fetch_geojson(full_addr: str, db_path: str, api_key: str):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT geojson FROM geocache WHERE raw_address = ?", (full_addr,))
        row = cursor.fetchone()
        if row: return json.loads(row[0]) if row[0] else None
            
        print(f"🔍 Поиск: {full_addr}...", end=" ", flush=True)
        geojson_str = fetch_polygon_from_visicom(full_addr, api_key)
        print("✅ OK" if geojson_str else "❌")
            
        cursor.execute("INSERT INTO geocache (raw_address, clean_address, geojson) VALUES (?, ?, ?)",
                       (full_addr, full_addr, geojson_str))
        conn.commit()
        return json.loads(geojson_str) if geojson_str else None

def process_map_file(file_path: str, db_path: str, api_key: str):
    df = pd.read_excel(file_path, sheet_name='2025', engine='odf', header=None)
    # ТЗ: Протяжка улиц вниз
    df[0] = df[0].replace(r'^\s*$', pd.NA, regex=True).ffill()
    
    # ТЗ: Поиск колонок месяцев
    month_names = ['січ', 'лют', 'бер', 'квіт', 'трав', 'черв', 'лип', 'серп', 'вер', 'жовт', 'лист', 'груд']
    month_cols = []
    for i in range(len(df.columns)):
        v0, v1 = str(df.iloc[0, i]).lower(), str(df.iloc[1, i]).lower()
        if any(m in v0 for m in month_names) or any(m in v1 for m in month_names):
            month_cols.append(i)

    # ТЗ: Цвета 2+1 (2 красных последних, 1 желтый перед ними)
    target_cols = month_cols[-3:] if len(month_cols) >= 3 else month_cols
    col_yellow = target_cols[-3] if len(target_cols) >= 3 else None
    cols_red = target_cols[-2:] if len(target_cols) >= 2 else target_cols

    features = []
    for idx in range(2, len(df)):
        row = df.iloc[idx]
        street, house = row[0], row[1]
        if pd.isna(house) or str(house).strip() == "": continue
        
        clean_addr = clean_address_for_api(street, house)
        
        # ТЗ: Если ячейка не пустая (любой символ) - обход был
        is_visited_red = any(pd.notna(row[c]) and str(row[c]).strip() != "" for c in cols_red)
        is_visited_yellow = pd.notna(row[col_yellow]) and str(row[col_yellow]).strip() != "" if col_yellow is not None else False
        
        color, status = "#adb5bd", "Обхода не было"
        if is_visited_red: color, status = "#dc3545", "Свежий обход"
        elif is_visited_yellow: color, status = "#ffc107", "Старый обход"

        feature = get_or_fetch_geojson(clean_addr, db_path, api_key)
        if feature:
            feature['properties'] = {'address': clean_addr, 'color': color, 'status': status}
            features.append(feature)

    print(f"\n🏁 Готово! Домов на карте: {len(features)}")
    return {"type": "FeatureCollection", "features": features}