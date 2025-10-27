import os
from ast import literal_eval

from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()


class Config:
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
    BOOKING_SPREADSHEET_ID = os.getenv("BOOKING_SPREADSHEET_ID")
    BOOKING_TASK_SPREADSHEET_ID = os.getenv("BOOKING_TASK_SPREADSHEET_ID")

    #FTP
    FTP_HOST = os.getenv("FTP_HOST")
    FTP_USER = os.getenv("FTP_USER")
    FTP_PASSWORD = os.getenv("FTP_PASSWORD")

    # Список наших аппартаментов - исправленная версия
    BOOKING_DATA_DIR="booking_files"
    TASK_DATA_DIR="task_files"
    SCHEDULER_DATA_DIR="scheduler"
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

    # Настройки логирования
    LOG_DIR = "logs"
    LOG_FILE = "service.log"
    LOG_ROTATION = "3 MB"  # Ротация при достижении 10 МБ
    LOG_RETENTION = 3  # Хранение 3 архивов

    # Урл сайта где формы
    REMOTE_WEB_APP_URL= "https://ci84606-wordpress-rdeld.tw1.ru"
    REMOTE_WEB_APP_CREATE_BOOKING_URL = "/?page_id=8"
    REMOTE_WEB_APP_BOOKING_Calculat_URL = "/booking_calculator.php"