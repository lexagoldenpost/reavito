import os

class Config:
    # Настройки PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1")

    # Настройки Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your_telegram_bot_token")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "your_chat_id")

    # Настройки Avito API
    AVITO_API_TOKEN = os.getenv("AVITO_API_TOKEN", "your_avito_api_token")

    # Настройки логирования
    LOG_DIR = "logs"
    LOG_FILE = "service.log"
    LOG_ROTATION = "10 MB"  # Ротация при достижении 10 МБ
    LOG_RETENTION = 3       # Хранение 3 архивов