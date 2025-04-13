import sys
import io
import asyncio
from typing import Dict, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telethon import TelegramClient, events
from telethon.tl.types import Message, PeerChat, User, Channel, PeerChannel
from common.config import Config
from common.logging_config import setup_logger
from models import ChannelKeyword, Base

# Устанавливаем UTF-8 кодировку для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = setup_logger("channel_monitor")

DATABASE_URL = f"postgresql+asyncpg://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"
TELEGRAM_SESSION_NAME = Config.TELEGRAM_API_SEND_BOOKING_ID+'_'+Config.TELEGRAM_SESSION_NAME

async_engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class ChannelMonitor:
  def __init__(self):
    self.api_id = Config.TELEGRAM_API_SEND_BOOKING_ID
    self.api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH
    self.phone = Config.TELEGRAM_SEND_BOOKING_PHONE
    self.target_group = Config.TARGET_GROUP

    # Словарь для хранения групп и их ключевых слов {group_name: {keywords}}
    self.group_keywords: Dict[str, Set[str]] = {}

    self.client = TelegramClient(
        TELEGRAM_SESSION_NAME,
        self.api_id,
        self.api_hash,
        system_version='4.16.30-vxCUSTOM'
    )

  async def load_group_keywords(self):
    """Загрузка групп и ключевых слов из БД"""
    try:
      async with AsyncSessionLocal() as session:
        result = await session.execute(select(ChannelKeyword))
        records = result.scalars().all()

        if not records:
          logger.error("В базе данных нет записей о группах")
          return False

        self.group_keywords.clear()
        for record in records:
          if not record.channel:
            continue

          group_name = record.channel.strip()
          keywords = {kw.strip().lower()
                      for kw in record.keywords.split(',')
                      if kw.strip()} if record.keywords else set()

          self.group_keywords[group_name] = keywords
          logger.info("Загружена группа: '%s' с ключевыми словами: %s",
                      group_name, keywords)

        return True

    except Exception as e:
      logger.error("Ошибка загрузки данных: %s", str(e), exc_info=True)
      return False

  async def print_active_dialogs(self):
      """Вывод информации о всех доступных диалогах (каналах и группах)"""
      try:
        dialogs = await self.client.get_dialogs()
        if not dialogs:
          logger.error("Не удалось получить список диалогов")
          return

        logger.info("Список всех доступных диалогов:")
        for dialog in dialogs:
          if not hasattr(dialog, "entity"):
            continue

          entity = dialog.entity

          # Определяем тип сущности
          if isinstance(entity, User):
            entity_type = "Пользователь"
          elif isinstance(entity, PeerChat):
            entity_type = "Группа"
          elif isinstance(entity, (Channel, PeerChannel)):
            entity_type = "Канал"
          else:
            entity_type = "Неизвестный тип"

          # Получаем информацию о доступности
          if getattr(entity, 'left', False):
            status = "Покинут"
          elif getattr(entity, 'kicked', False):
            status = "Заблокирован"
          else:
            status = "Активен"

          name = getattr(entity, 'title', None) or getattr(entity, 'username',
                                                           None) or "Без названия"

          logger.info("- %s: '%s' (ID: %d, Тип: %s, Статус: %s)",
                      "Диалог", name, entity.id, entity_type, status)

      except Exception as e:
        logger.error("Ошибка получения списка диалогов: %s", str(e),
                     exc_info=True)

  async def print_active_groups(self):
    """Вывод информации о доступных группах"""
    try:
      dialogs = await self.client.get_dialogs()
      if not dialogs:
        logger.error("Не удалось получить список диалогов")
        return

      logger.info("Список доступных групп:")
      for dialog in dialogs:
        if not hasattr(dialog, "entity"):
          continue

        entity = dialog.entity

        # Проверяем разными способами, что это группа
        is_group = False
        if dialog.is_group:
          is_group = True
        elif isinstance(entity, PeerChat):
          is_group = True
        elif hasattr(entity, 'megagroup') and entity.megagroup:
          is_group = True
        elif hasattr(entity, 'broadcast') and not entity.broadcast:
          is_group = True

        if not is_group:
          continue

        status = ""
        if getattr(entity, 'left', False):
          status = " (Покинута)"
        elif getattr(entity, 'kicked', False):
          status = " (Заблокирована)"

        name = getattr(entity, 'title', "Без названия")
        logger.info("- Группа: '%s'%s (ID: %d, Тип: %s)",
                    name, status, entity.id, type(entity))

    except Exception as e:
      logger.error("Ошибка получения списка групп: %s", str(e), exc_info=True)

  async def setup_monitoring(self):
    """Настройка обработчика сообщений"""
    if not await self.load_group_keywords():
      return False

    await self.print_active_groups()

    @self.client.on(events.NewMessage())
    async def handler(event):
      try:
        if not event.is_group:
          return
        message = event.message
        if not message or not message.text:
          return

        # Получаем полную информацию о чате
        chat = await event.get_chat()
        if not chat:
          logger.debug("Не удалось получить информацию о чате")
          return

        # Логируем тип чата для диагностики
        logger.debug("Тип чата: %s, Атрибуты: %s", type(chat), dir(chat))

        # Получаем название группы
        group_name = getattr(chat, 'title', None)
        if not group_name:
          logger.debug("Не удалось получить название группы")
          return

        logger.debug("Обработка сообщения из группы: %s", group_name)

        # Проверяем, что группа есть в нашей БД
        if group_name not in self.group_keywords:
          logger.debug("Группа '%s' не найдена в БД", group_name)
          return

        # Проверяем ключевые слова
        keywords = self.group_keywords[group_name]
        if not keywords:
          logger.debug("Для группы '%s' нет ключевых слов", group_name)
          return

        text_lower = message.text.lower()
        if any(keyword in text_lower for keyword in keywords):
          logger.info("Найдено ключевое слово в группе '%s'", group_name)
          await self.forward_to_group(message, group_name)

      except Exception as e:
        logger.error("Ошибка обработки сообщения: %s", str(e), exc_info=True)

    return True

  async def forward_to_group(self, message: Message, group_name: str):
    """Пересылка сообщения в целевую группу"""
    try:
      # Получаем полную информацию о целевом чате
      try:
        target_entity = await self.client.get_entity(self.target_group)
      except Exception as e:
        logger.error("Ошибка получения целевого чата '%s': %s",
                     self.target_group, str(e))
        return

      # Получаем информацию об исходном чате
      try:
        chat = await message.get_chat()
        chat_id = chat.id
      except Exception as e:
        logger.error("Ошибка получения информации об исходном чате: %s", str(e))
        chat_id = 0  # Используем 0 если не удалось получить ID

      # Формируем текст сообщения
      message_text = (
        f"🔍 Найдено соответствие в группе {group_name}\n\n"
        f"📄 Текст сообщения:\n{message.text}\n\n"
      )

      # Добавляем ссылку только если есть chat_id
      if chat_id:
        message_text += f"🔗 Ссылка: https://t.me/c/{chat_id}/{message.id}"
      else:
        message_text += "⚠️ Не удалось получить ссылку на сообщение"

      # Отправляем сообщение
      await self.client.send_message(
          entity=target_entity,
          message=message_text,
          link_preview=False
      )
      logger.info("Сообщение из группы '%s' переслано в '%s'",
                  group_name, self.target_group)

    except Exception as e:
      logger.error("Ошибка при пересылке сообщения: %s", str(e), exc_info=True)

  async def start(self):
    """Запуск мониторинга"""
    try:
      await self.client.start(self.phone)
      logger.info("Клиент Telegram успешно запущен")

      if not await self.setup_monitoring():
        logger.error("Не удалось инициализировать мониторинг")
        return

      await self.client.run_until_disconnected()
    except Exception as e:
      logger.error("Ошибка запуска: %s", str(e), exc_info=True)
    finally:
      await self.client.disconnect()
      logger.info("Клиент Telegram отключен")

  def run(self):
    """Синхронный запуск мониторинга"""
    try:
      with self.client:
        self.client.loop.run_until_complete(self.start())
    except Exception as e:
      logger.error("Критическая ошибка: %s", str(e), exc_info=True)
      raise


if __name__ == "__main__":
  monitor = ChannelMonitor()
  monitor.run()