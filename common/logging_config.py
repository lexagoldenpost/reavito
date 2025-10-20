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

    # Ротация логов с UTF-8 кодировкой
    handler = RotatingFileHandler(
        os.path.join(Config.LOG_DIR, f"{service_name}.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=Config.LOG_RETENTION,
        encoding='utf-8'  # Добавьте эту строку
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Также добавим консольный handler с обработкой ошибок кодировки
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Безопасный форматтер для консоли (заменяет проблемные символы)
    class SafeFormatter(logging.Formatter):
        def format(self, record):
            try:
                return super().format(record)
            except UnicodeEncodeError:
                # Заменяем проблемные символы при выводе в консоль
                message = record.getMessage()
                safe_message = message.encode('utf-8', errors='replace').decode('utf-8')
                record.msg = safe_message
                return super().format(record)

    console_formatter = SafeFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Отключаем логгер Werkzeug (по умолчанию Flask использует его)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)

    return logger