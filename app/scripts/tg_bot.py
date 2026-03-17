import os
import requests
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.graphs import generate_stats_chart

bot_token = os.getenv("TG_BOT_TOKEN")
chat_id = os.getenv("TG_CHAT_ID")
cf_zone_id = os.getenv("CF_ZONE_ID")
cf_api_token = os.getenv("CF_API_TOKEN")

bot = telebot.TeleBot(bot_token) if bot_token else None

def send_telegram_alert(message: str):
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
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

def get_cloudflare_stats():
    if not cf_zone_id or not cf_api_token:
        return "❌ Помилка: Не налаштовані CF_ZONE_ID або CF_API_TOKEN"
    
    url = "https://api.cloudflare.com/client/v4/graphql"
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "application/json"
    }
    
    # Вираховуємо дату 7 днів тому
    from datetime import datetime, timedelta
    since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Формуємо правильний GraphQL запит
    query = f"""
    query {{
      viewer {{
        zones(filter: {{zoneTag: "{cf_zone_id}"}}) {{
          httpRequests1dGroups(limit: 10, filter: {{date_geq: "{since_date}"}}) {{
            sum {{
              requests
              threats
            }}
          }}
        }}
      }}
    }}
    """
    
    try:
        # GraphQL завжди використовує POST запити
        r = requests.post(url, headers=headers, json={"query": query}, timeout=10)
        data = r.json()
        
        # Перевірка на помилки в новому форматі
        if "errors" in data and data["errors"]:
            err_msg = data["errors"][0].get("message", "Невідома помилка GraphQL")
            return f"❌ Відмова Cloudflare: {err_msg}"
            
        zones = data.get("data", {}).get("viewer", {}).get("zones", [])
        if zones:
            groups = zones[0].get("httpRequests1dGroups", [])
            
            # Сумуємо всі дні
            total_requests = sum(g.get("sum", {}).get("requests", 0) for g in groups)
            total_threats = sum(g.get("sum", {}).get("threats", 0) for g in groups)
            
            return f"☁️ <b>CLOUDFLARE SHIELD (Last 7 days)</b>\n🛡 Заблоковано загроз: <b>{total_threats}</b>\n🌐 Загалом запитів: <b>{total_requests}</b>"
        else:
            return "❌ Немає даних від Cloudflare (перевірте Zone ID)"
            
    except Exception as e:
        return f"❌ Збій коду: {e}"

if bot:
    @bot.message_handler(commands=['stats'])
    def handle_stats(message):
        if str(message.chat.id) != str(chat_id):
            return
        
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("1 Week", callback_data="stats_7"),
            InlineKeyboardButton("1 Month", callback_data="stats_30"),
            InlineKeyboardButton("1 Year", callback_data="stats_365")
        )
        bot.reply_to(message, "📊 <b>Оберіть період для аналітики інцидентів:</b>", reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('stats_'))
    def callback_stats(call):
        days = int(call.data.split('_')[1])
        bot.answer_callback_query(call.id, "Генерація графіка...")
        
        photo = generate_stats_chart(days)
        caption = f"🛡 <b>SECURITY REPORT ({days} DAYS)</b>\nСтатистика відбитих атак з SQLite."
        
        bot.send_photo(call.message.chat.id, photo, caption=caption, parse_mode="HTML")

    @bot.message_handler(commands=['log'])
    def handle_log(message):
        if str(message.chat.id) != str(chat_id):
            return
        stats_msg = get_cloudflare_stats()
        bot.reply_to(message, stats_msg, parse_mode="HTML")

def start_bot_polling():
    if bot:
        print("Starting Telegram SOC Bot listener...")
        bot.infinity_polling()