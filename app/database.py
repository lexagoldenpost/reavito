from flask_sqlalchemy import SQLAlchemy
from flask import current_app


db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    with app.app_context():
        current_app.logger.info("Initializing database...")
        db.create_all()  # Создаем таблицы, если их нет
        current_app.logger.info("Database initialized successfully.")