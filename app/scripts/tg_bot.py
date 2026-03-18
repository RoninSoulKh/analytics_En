import os
import requests
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.graphs import generate_cf_chart

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
        f"<b>[СИСТЕМНЕ ПОВІДОМЛЕННЯ, СЕР]</b>\n"
        f"--------------------------------\n"
        f"Виявлено несанкціоновану активність:\n"
        f"{message}\n"
        f"--------------------------------\n"
        f"СТАТУС: Загрозу нейтралізовано."
    )

    payload = {
        "chat_id": chat_id,
        "text": full_text,
        "parse_mode": "HTML"
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Помилка відправки протоколу: {str(e)}")

def get_cloudflare_stats():
    if not cf_zone_id or not cf_api_token:
        return "⚠️ Сер, модулі Cloudflare не підключені. Перевірте змінні середовища."
    
    url = "https://api.cloudflare.com/client/v4/graphql"
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "application/json"
    }
    
    from datetime import datetime, timedelta
    since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
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
        r = requests.post(url, headers=headers, json={"query": query}, timeout=10)
        data = r.json()
        
        if "errors" in data and data["errors"]:
            return "⚠️ Сер, зовнішній щит не відповідає на запит."
            
        zones = data.get("data", {}).get("viewer", {}).get("zones", [])
        if zones:
            groups = zones[0].get("httpRequests1dGroups", [])
            total_requests = sum(g.get("sum", {}).get("requests", 0) for g in groups)
            total_threats = sum(g.get("sum", {}).get("threats", 0) for g in groups)
            
            return (f"🛡 <b>Звіт зовнішнього щита (останні 7 днів), сер:</b>\n\n"
                    f"🛑 Відбито атак: <b>{total_threats}</b>\n"
                    f"🌐 Загальний трафік: <b>{total_requests}</b>\n\n"
                    f"Системи працюють у штатному режимі.")
        else:
            return "⚠️ Сер, дані відсутні. Можливо, варто перевірити ідентифікатор зони."
            
    except Exception as e:
        return f"⚠️ Виникла системна помилка, сер: {e}"

if bot:
    @bot.message_handler(commands=['stats'])
    def handle_stats(message):
        if str(message.chat.id) != str(chat_id):
            return
        
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("1 Тиждень", callback_data="stats_week"),
            InlineKeyboardButton("1 Місяць", callback_data="stats_month"),
            InlineKeyboardButton("1 Рік", callback_data="stats_year")
        )
        bot.reply_to(message, "Запускаю протокол аналітики. <b>Який період вас цікавить, сер?</b>", reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('stats_'))
    def callback_stats(call):
        period = call.data.split('_')[1]
        bot.answer_callback_query(call.id, "Обробляю дані масиву, сер...")
        
        photo = generate_cf_chart(period, cf_zone_id, cf_api_token)
        
        if not photo:
            bot.send_message(call.message.chat.id, "⚠️ Сер, не вдалося отримати телеметрію із зовнішніх сенсоров Cloudflare.")
            return

        period_names = {"week": "тиждень", "month": "місяць", "year": "рік"}
        caption = f"🛡 <b>Ось ваша візуалізація атак за {period_names.get(period, 'період')}, сер.</b>\nУсі системи захисту активовані."
        
        bot.send_photo(call.message.chat.id, photo, caption=caption, parse_mode="HTML")

    @bot.message_handler(commands=['log'])
    def handle_log(message):
        if str(message.chat.id) != str(chat_id):
            return
        stats_msg = get_cloudflare_stats()
        bot.reply_to(message, stats_msg, parse_mode="HTML")

def start_bot_polling():
    if bot:
        print("J.A.R.V.I.S. SOC protocol initialized...")
        bot.infinity_polling()