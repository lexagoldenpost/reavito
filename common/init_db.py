# init_db.py
import asyncio
from common.database import Base, engine, async_engine
from common.logging_config import setup_logger

logger = setup_logger("init_db")


async def async_create_tables():
  """
    Асинхронно создает все таблицы в базе данных, если они еще не существуют.
    """
  try:
    # Импортируем все модели, чтобы они были зарегистрированы в Base.metadata
    try:
      from avito_message_in.models import Message  # noqa
      logger.debug("Импортированы модели из avito_message_in")
    except ImportError:
      logger.warning("Модуль avito_message_in не найден")

    try:
      from sync_db_google_sheets.models import (
        Booking, Notification, Chat, ChannelKeyword, TelethonSession  # noqa
      )
      logger.debug("Импортированы модели из sync_db_google_sheets")
    except ImportError:
      logger.warning("Модуль sync_db_google_sheets не найден")

    # Для синхронного движка
    logger.info("Создание таблиц с синхронным движком...")
    Base.metadata.create_all(bind=engine)

    # Для асинхронного движка (альтернативный вариант)
    async with async_engine.begin() as conn:
      logger.info("Создание таблиц с асинхронным движком...")
      await conn.run_sync(Base.metadata.create_all)

    logger.info("Все таблицы успешно созданы.")
  except Exception as e:
    logger.error(f"Ошибка при создании таблиц: {e}")
    raise


def create_tables():
  """
    Синхронная обертка для асинхронного создания таблиц
    """
  asyncio.run(async_create_tables())


if __name__ == "__main__":
  create_tables()