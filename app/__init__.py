#инициализация Flask-приложения
from flask import Flask
from .database import init_db
from .routes.avito_msg_routes import avito_msg_bp
from .logger import setup_logger

def create_app():
    app = Flask(__name__)

    # Загружаем конфигурацию
    app.config.from_object('app.config.Config')

    # Инициализируем базу данных
    init_db(app)

    # Настраиваем логгер
    setup_logger(app)

    # Регистрируем Blueprint
    app.register_blueprint(avito_msg_bp, url_prefix='/api/avito')

    return app