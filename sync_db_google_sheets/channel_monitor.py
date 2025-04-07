import sys
import io
import asyncio
from typing import List, Dict, Set, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telethon import TelegramClient, events
from telethon.tl.types import Message, Channel, PeerChannel, PeerChat, User
from common.config import Config
from common.logging_config import setup_logger
from models import ChannelKeyword, Base

# Устанавливаем UTF-8 кодировку для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = setup_logger("channel_monitor")

DATABASE_URL = f"postgresql+asyncpg://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"

async_engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class ChannelMonitor:
  def __init__(self):
    self.api_id = Config.TELEGRAM_API_SEARCH_ID
    self.api_hash = Config.TELEGRAM_API_SEARCH_HASH
    self.phone = Config.TELEGRAM_SEARCH_PHONE
    self.target_group = Config.TARGET_GROUP

    self.channel_keywords: Dict[str, Set[str]] = {}
    self.active_entities: Set[str] = set()
    self.monitored_entities: List[Union[Channel, PeerChannel, PeerChat]] = []

    self.client = TelegramClient(
        'channel_monitor_session',
        self.api_id,
        self.api_hash,
        system_version='4.16.30-vxCUSTOM'
    )

  async def load_channel_keywords(self):
    """Загрузка каналов и ключевых слов из БД"""
    try:
      async with AsyncSessionLocal() as session:
        result = await session.execute(select(ChannelKeyword))
        records = result.scalars().all()

        if not records:
          logger.error("В базе данных нет записей о каналах/группах")
          return False

        self.channel_keywords.clear()
        for record in records:
          if not record.channel:
            continue

          keywords = {kw.strip().lower()
                      for kw in record.keywords.split(',')
                      if kw.strip()} if record.keywords else set()

          self.channel_keywords[record.channel] = keywords

        logger.info("Загружено %d сущностей с ключевыми словами",
                    len(self.channel_keywords))
        return True

    except Exception as e:
      logger.error("Ошибка загрузки данных: %s", str(e), exc_info=True)
      return False

  async def get_active_entities(self):
    """Получение активных каналов и групп"""
    try:
      dialogs = await self.client.get_dialogs()
      if not dialogs:
        logger.error("Не удалось получить список диалогов")
        return []

      active_entities = []
      for dialog in dialogs:
        if not hasattr(dialog, "entity"):
          continue

        entity = dialog.entity

        if isinstance(entity, User):
          continue

        if isinstance(entity, (Channel, PeerChannel, PeerChat)):
          if getattr(entity, 'left', False) or getattr(entity, 'kicked', False):
            continue

          name = getattr(entity, 'username', None) or getattr(entity, 'title',
                                                              None)
          if name:
            active_entities.append((name, entity))

      if not active_entities:
        logger.error("Активные каналы/группы не найдены")
      else:
        logger.info("Найдено активных сущностей: %d", len(active_entities))

      return active_entities

    except Exception as e:
      logger.error("Ошибка получения сущностей: %s", str(e), exc_info=True)
      return []

  async def setup_monitoring(self):
    """Настройка мониторинга каналов и групп"""
    if not await self.load_channel_keywords():
      return False

    active_entities = await self.get_active_entities()
    if not active_entities:
      return False

    self.monitored_entities = []
    self.active_entities = set()
    matched = 0

    def normalize(name):
      return name.replace("@", "").replace("https://t.me/",
                                           "").strip().lower() if name else ""

    db_entities = {normalize(name): name for name in
                   self.channel_keywords.keys()}

    for entity_name, entity in active_entities:
      try:
        norm_name = normalize(entity_name)

        if norm_name in db_entities:
          self.monitored_entities.append(entity)
          self.active_entities.add(entity_name)
          matched += 1

          entity_type = "группа" if isinstance(entity, PeerChat) else "канал"
          logger.info("Сопоставлена %s: Telegram: '%s' ↔ БД: '%s'",
                      entity_type, entity_name, db_entities[norm_name])
      except Exception as e:
        logger.warning("Ошибка обработки сущности %s: %s", entity_name, str(e))

    if not matched:
      logger.error("Совпадений не найдено. Проверьте:")
      logger.info("Сущности в БД: %s", list(self.channel_keywords.keys()))
      logger.info("Активные сущности: %s",
                  [name for name, _ in active_entities])
      return False

    self.client.add_event_handler(
        self.handle_new_message,
        events.NewMessage(chats=self.monitored_entities)
    )

    logger.info("Мониторинг запущен для %d сущностей: %s", matched,
                list(self.active_entities))
    return True

  def contains_keywords(self, entity_name: str, text: str) -> bool:
    if not text or not entity_name:
      return False

    if entity_name not in self.channel_keywords:
      return False

    text_lower = text.lower()
    keywords = self.channel_keywords[entity_name]

    return any(keyword in text_lower for keyword in keywords)

  async def forward_to_group(self, message: Message):
    try:
      chat_title = getattr(message.chat, 'title', 'Без названия')
      target_entity = await self.client.get_entity(self.target_group)

      entity_type = "группе" if isinstance(message.chat, PeerChat) else "канале"

      await self.client.send_message(
          target_entity,
          "Найдено соответствие в {} {}\n\nТекст сообщения:\n{}\n\nСсылка: https://t.me/c/{}/{}".format(
              entity_type, chat_title, message.text, message.chat.id, message.id
          ),
          link_preview=False
      )
      logger.info("Сообщение переслано в группу %s", self.target_group)

    except Exception as e:
      logger.error("Ошибка при пересылке: %s", str(e), exc_info=True)

  async def handle_new_message(self, event):
    try:
      message = event.message
      if not message or not message.text:
        return

      chat = event.chat
      entity_name = getattr(chat, 'title', None) or getattr(chat, 'username',
                                                            None)
      if not entity_name or entity_name not in self.active_entities:
        return

      entity_type = "группы" if isinstance(chat, PeerChat) else "канала"
      logger.debug("Новое сообщение из %s %s: %s", entity_type, entity_name,
                   message.text[:50])

      if self.contains_keywords(entity_name, message.text):
        logger.info("Найдено соответствие в %s %s", entity_type, entity_name)
        await self.forward_to_group(message)

    except Exception as e:
      logger.error("Ошибка обработки сообщения: %s", str(e), exc_info=True)

  async def start(self):
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
    try:
      with self.client:
        self.client.loop.run_until_complete(self.start())
    except Exception as e:
      logger.error("Критическая ошибка: %s", str(e), exc_info=True)
      raise


if __name__ == "__main__":
  monitor = ChannelMonitor()
  monitor.run()