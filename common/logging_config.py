import logging
from logging.handlers import RotatingFileHandler
import os
from common.config import Config

def setup_logger(service_name):
    # Создаем директорию для логов, если её нет
    if not os.path.exists(Config.LOG_DIR):
        os.makedirs(Config.LOG_DIR)

    # Настройка логгера
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.DEBUG)

    # Формат логов
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Ротация логов
    handler = RotatingFileHandler(
        os.path.join(Config.LOG_DIR, f"{service_name}.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=Config.LOG_RETENTION
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Отключаем логгер Werkzeug (по умолчанию Flask использует его)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)

    return logger