from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from common.config import Config

# Подключение к PostgreSQL
DATABASE_URL = f"postgresql://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"

# Создание движка SQLAlchemy
engine = create_engine(DATABASE_URL)

# Создание фабрики сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей SQLAlchemy
Base = declarative_base()

# Функция для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Функция для создания всех таблиц
def create_tables():
    """
    Создает все таблицы в базе данных, если они еще не существуют.
    """
    try:
        # Импортируем все модели, чтобы они были зарегистрированы в Base.metadata
        from avito_message_in.models import Message  # Пример для микросервиса 1
        # Добавьте импорты для моделей других микросервисов, если они есть
        #from scenario_bot.models import Message_Scenario
        from sync_db_google_sheets.models import Booking

        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        print("Все таблицы успешно созданы.")
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")

# Вызов функции для создания таблиц при инициализации
create_tables()