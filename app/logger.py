import logging
import os
from logging.handlers import RotatingFileHandler

# Путь к папке для логов
log_dir = "logs"

# Создаем папку для логов, если она не существует
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

def setup_logger(app):
    # Формат логов
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    log_file = os.path.join(log_dir, app.config['LOG_FILE'])
    # Настройка файлового логгера
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1024 * 1024, backupCount=10
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(app.config['LOG_LEVEL'])

    # Настройка логгера приложения
    app.logger.addHandler(file_handler)
    app.logger.setLevel(app.config['LOG_LEVEL'])

    # Отключаем логгер Werkzeug (по умолчанию Flask использует его)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)