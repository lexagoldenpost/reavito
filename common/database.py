# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from common.config import Config

# Настройки подключения и создание движков остаются без изменений
DATABASE_URL = f"postgresql://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"
ASYNC_DATABASE_URL = f"postgresql+asyncpg://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"

engine = create_engine(DATABASE_URL)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

# Функции для получения сессий базы данных
def get_db():
    """Синхронный генератор сессий"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def async_get_db():
    """Асинхронный генератор сессий"""
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()

# # Функция для создания всех таблиц
# def create_tables():
#     """
#     Создает все таблицы в базе данных, если они еще не существуют.
#     """
#     try:
#         # Импортируем все модели, чтобы они были зарегистрированы в Base.metadata
#         from avito_message_in.models import Message  # Пример для микросервиса 1
#         # Добавьте импорты для моделей других микросервисов, если они есть
#         #from scenario_bot.models import Message_Scenario
#         from sync_db_google_sheets.models import Booking, Notification, Chat, ChannelKeyword, TelethonSession
#
#         # Создаем все таблицы
#         Base.metadata.create_all(bind=engine)
#         print("Все таблицы успешно созданы.")
#     except Exception as e:
#         print(f"Ошибка при создании таблиц: {e}")
#
# # Асинхронная версия создания таблиц
# async def async_create_tables():
#     """Асинхронное создание таблиц"""
#     async with async_engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     print("Асинхронное создание таблиц завершено")
#
# # Вызов функции для создания таблиц при инициализации
# create_tables()