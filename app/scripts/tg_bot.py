import os
import requests

def send_telegram_alert(message: str):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Формуємо суворий системний звіт
    full_text = (
        f"<b>[SYSTEM_SECURITY_LOG]</b>\n"
        f"--------------------------------\n"
        f"{message}\n"
        f"--------------------------------\n"
        f"STATUS: ACTION_BLOCKED"
    )

    payload = {
        "chat_id": chat_id,
        "text": full_text,
        "parse_mode": "HTML"
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"FAILED_TO_SEND_LOG: {str(e)}")