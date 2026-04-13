import re

def clean_address(raw_address: str) -> str:
    """Очищает суржик и приводит адрес к формату Visicom"""
    if not isinstance(raw_address, str):
        return ""
        
    addr = raw_address.strip()
    
    # Убираем "д.", "д ", "буд." и оставляем только номер
    addr = re.sub(r'(?i)\b(д\.|д\s|буд\.|б\.)\s*', '', addr)
    
    # Приводим типы улиц к нормальному виду
    addr = re.sub(r'(?i)\bпер\.', 'пров. ', addr)
    addr = re.sub(r'(?i)\bул\.', 'вул. ', addr)
    
    # Убираем лишние пробелы перед дефисами/дробями
    addr = re.sub(r'\s+-\s+', '-', addr)
    addr = re.sub(r'\s+/\s+', '/', addr)
    
    # Убираем двойные пробелы
    addr = ' '.join(addr.split())
    
    # Если адрес не пустой, добавляем город
    if addr:
        return f"м. Харків, {addr}"
    return ""

# Блок для локального теста
if __name__ == "__main__":
    test_addresses = [
        "пер.ИСТОМИНСКИЙ 2-Й д.9/2",
        "пров. КАУНАСЬКИЙ д.10А",
        "пер.КОНЮШЕННЫЙ  д.10",
        "вул.Леоніда Бикова д. 73а"
    ]
    for a in test_addresses:
        print(f"Було:  {a}\nСтало: {clean_address(a)}\n")