# channel_monitor.py
import asyncio
from typing import Dict, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telethon import TelegramClient, events
from telethon.tl.types import Message
from common.config import Config
from common.logging_config import setup_logger
from models import ChannelKeyword
from postgres_session import PostgresSession

# Настройка логгера
logger = setup_logger("channel_monitor")

# Конфигурация сессии Telegram
TELEGRAM_SESSION_NAME = f"{Config.TELEGRAM_API_SEND_BOOKING_ID}_{Config.TELEGRAM_SESSION_NAME}"

# Глобальные объекты для работы с БД
async_engine = create_async_engine(
    f"postgresql+asyncpg://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@"
    f"{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}",
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


class ChannelMonitor:
    def __init__(self):
        """Инициализация монитора каналов"""
        self.api_id = Config.TELEGRAM_API_SEND_BOOKING_ID
        self.api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH
        self.phone = Config.TELEGRAM_SEND_BOOKING_PHONE
        self.target_group = Config.TARGET_GROUP
        self.group_keywords: Dict[str, Set[str]] = {}
        self.client = None
        self.telethon_session = None

    async def initialize(self) -> bool:
        """Инициализация монитора"""
        try:
            # Инициализация сессии и клиента Telegram
            self.telethon_session = PostgresSession(
                session_name=TELEGRAM_SESSION_NAME
            )

            self.client = TelegramClient(
                self.telethon_session,
                self.api_id,
                self.api_hash,
                system_version='4.16.30-vxCUSTOM',
                connection_retries=5,
                request_retries=3,
                auto_reconnect=True
            )

            # Подключение к Telegram
            await self.client.start(self.phone)
            logger.info("Telegram client started")

            # Сохранение данных сессии в БД
            await self.telethon_session.save_updates()
            logger.debug("Telegram session saved to database")

            # Загрузка ключевых слов
            if not await self._load_keywords():
                raise RuntimeError("Keyword loading failed")

            # Настройка обработчиков
            self._setup_handlers()
            logger.info("Channel monitor initialized")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    async def _load_keywords(self) -> bool:
        """Загрузка ключевых слов из БД"""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(ChannelKeyword))
                self.group_keywords = {
                    record.channel.strip(): {
                        kw.strip().lower()
                        for kw in record.keywords.split(',')
                        if kw.strip()
                    }
                    for record in result.scalars()
                    if record.channel
                }
                logger.debug(f"Loaded {len(self.group_keywords)} keyword groups")
                return True
        except Exception as e:
            logger.error(f"Keyword loading error: {e}", exc_info=True)
            return False

    def _setup_handlers(self):
        """Настройка обработчиков сообщений"""

        @self.client.on(events.NewMessage())
        async def message_handler(event):
            try:
                if not await self._should_process_message(event):
                    return

                chat = await event.get_chat()
                message = event.message
                group_name = getattr(chat, 'title', None)
                group_id = str(chat.id) if hasattr(chat, 'id') else None

                if matched_keywords := self._find_matching_keywords(
                    group_name, group_id, message.text
                ):
                    await self._forward_message(message, group_name or f"ID:{group_id}")
                    logger.info(f"Matched keywords: {matched_keywords}")

            except Exception as e:
                logger.error(f"Message handling error: {e}", exc_info=True)

    async def _should_process_message(self, event) -> bool:
        """Проверка, нужно ли обрабатывать сообщение"""
        return (
            event.is_group
            and event.message
            and event.message.text
            and await event.get_chat()
        )

    def _find_matching_keywords(self, group_name: str, group_id: str,
                              text: str) -> Set[str]:
        """Поиск совпадений ключевых слов"""
        text_lower = text.lower()
        matched_keywords = set()

        for identifier, keywords in self.group_keywords.items():
            if (group_name and identifier == group_name) or (
                group_id and identifier == group_id):
                for phrase in keywords:
                    phrase_words = [w.strip() for w in phrase.split()]
                    words = [w.strip() for w in text_lower.split()]

                    if any(
                        words[i:i + len(phrase_words)] == phrase_words
                        for i in range(len(words) - len(phrase_words) + 1)
                    ):
                        matched_keywords.add(phrase)

        return matched_keywords

    async def _forward_message(self, message: Message, source_name: str):
        """Пересылка сообщения в целевой чат"""
        try:
            target_entity = await self.client.get_entity(self.target_group)
            chat = await message.get_chat()
            chat_id = chat.id if hasattr(chat, 'id') else 0

            await self.client.send_message(
                entity=target_entity,
                message=(
                    f"🔍 Сообщение из: {source_name}\n\n"
                    f"📄 Текст:\n{message.text}\n\n"
                    f"🔗 Ссылка: https://t.me/c/{chat_id}/{message.id}" if chat_id else ""
                ),
                link_preview=False
            )
            logger.info(f"Forwarded message from {source_name}")

        except Exception as e:
            logger.error(f"Message forwarding error: {e}", exc_info=True)

    async def run(self):
        """Основной цикл работы"""
        try:
            if not await self.initialize():
                raise RuntimeError("Initialization failed")

            logger.info("Starting channel monitoring")
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы"""
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                logger.info("Telegram client disconnected")
        except Exception as e:
            logger.error(f"Shutdown error: {e}", exc_info=True)


async def main():
    """Асинхронная точка входа"""
    monitor = ChannelMonitor()
    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await monitor.shutdown()


if __name__ == "__main__":
    asyncio.run(main())