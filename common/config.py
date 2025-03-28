import os
from dotenv import load_dotenv
from ast import literal_eval

# Загружаем переменные окружения из файла .env
load_dotenv()

class Config:
    # Настройки PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

    # Настройки Telegram Bot
    TELEGRAM_BOOKING_BOT_TOKEN = os.getenv("TELEGRAM_BOOKING_BOT_TOKEN")
    ALLOWED_TELEGRAM_USERNAMES = literal_eval(os.getenv("ALLOWED_TELEGRAM_USERNAMES", "[]"))
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    TELEGRAM_BOT_NAME = os.getenv("TELEGRAM_BOT_NAME")
    TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

    # Настройки Avito API
    AVITO_CLIENT_ID = os.getenv("AVITO_CLIENT_ID")
    AVITO_CLIENT_SECRET = os.getenv("AVITO_CLIENT_SECRET")
    AVITO_USER_ID = os.getenv("AVITO_USER_ID")
    AVITO_TOKEN_URL = os.getenv("AVITO_TOKEN_URL")
    AVITO_REFRESH_TOKEN_URL = os.getenv("AVITO_REFRESH_TOKEN_URL")
    AVITO_SEND_CHAT_URL = os.getenv("AVITO_SEND_CHAT_URL")

    # Данные о Google Sheet
    # Расположение credentials
    SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
    # ID Google Sheet документа
    SAMPLE_SPREADSHEET_ID = os.getenv("SAMPLE_SPREADSHEET_ID")
    NOTIFICATIONS_SPREADSHEET_ID = os.getenv("NOTIFICATIONS_SPREADSHEET_ID")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

    # Настройки логирования
    LOG_DIR = "logs"
    LOG_FILE = "service.log"
    LOG_ROTATION = "10 MB"  # Ротация при достижении 10 МБ
    LOG_RETENTION = 3       # Хранение 3 архивов