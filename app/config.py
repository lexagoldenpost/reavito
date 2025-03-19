#конфигурация приложения
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class Config:
  # Секретный ключ из кабинета Avito
    AVITO_SECRET = os.getenv('AVITO_CLIENT_SECRET')
  # БД
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

  # Настройки логгера
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_FILE = os.getenv("LOG_FILE", "lapka_bot.log")