import os
from ast import literal_eval

from dotenv import load_dotenv

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
    TELEGRAM_CHAT_NOTIFICATION_ID = literal_eval(os.getenv("TELEGRAM_CHAT_NOTIFICATION_ID", "[]"))
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    TELEGRAM_BOT_NAME = os.getenv("TELEGRAM_BOT_NAME")
    TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

    # Настройки Telegram User для поиска каналов
    TELEGRAM_API_SEARCH_ID = os.getenv("TELEGRAM_API_SEARCH_ID")
    TELEGRAM_API_SEARCH_HASH = os.getenv("TELEGRAM_API_SEARCH_HASH")
    TELEGRAM_SEARCH_PHONE = os.getenv("TELEGRAM_SEARCH_PHONE")
    TARGET_GROUP = os.getenv("TARGET_GROUP")

    TELEGRAM_SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME")
    IMAGES_FOLDER = os.getenv("IMAGES_FOLDER")

    # Настройки Telegram User для отправки в каналы брониваний
    TELEGRAM_API_SEND_BOOKING_ID = os.getenv("TELEGRAM_API_SEND_BOOKING_ID")
    TELEGRAM_API_SEND_BOOKING_HASH = os.getenv("TELEGRAM_API_SEND_BOOKING_HASH")
    TELEGRAM_SEND_BOOKING_PHONE = os.getenv("TELEGRAM_SEND_BOOKING_PHONE")

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

    #Настройки шедуллера
    SCHEDULER_PERIOD = float(os.getenv("SCHEDULER_PERIOD"))  # период в минутах
    IS_SYNC_BOOKING = os.getenv("IS_SYNC_BOOKING") #Синхронизировать бронирования, только для одного компа, чтобы БД была норм иначе поедут ИД, для тесмтовых делаем бекапы