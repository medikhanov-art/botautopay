import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

if not BOT_TOKEN:
    raise ValueError("❌ Ошибка: Не найден BOT_TOKEN в .env файле!")