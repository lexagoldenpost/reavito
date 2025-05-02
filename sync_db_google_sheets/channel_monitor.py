import sys
import io
import asyncio
from pathlib import Path
from typing import Dict, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import Message, PeerChat, User, Channel, PeerChannel
from common.config import Config
from common.logging_config import setup_logger
from models import ChannelKeyword, Base

# Устанавливаем UTF-8 кодировку для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = setup_logger("channel_monitor")

DATABASE_URL = f"postgresql+asyncpg://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"
TELEGRAM_SESSION_NAME = Config.TELEGRAM_API_SEND_BOOKING_ID + '_' + Config.TELEGRAM_SESSION_NAME

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

    async def print_user_subscriptions(self):
        """Вывод всех групп и каналов, на которые подписан пользователь"""
        try:
            logger.info("Получение списка всех групп и каналов пользователя...")
            dialogs = await self.client.get_dialogs()

            if not dialogs:
                logger.warning("Не удалось получить список диалогов или список пуст")
                return

            logger.info("=== Список всех групп и каналов пользователя ===")
            for dialog in dialogs:
                if not hasattr(dialog, "entity"):
                    continue

                entity = dialog.entity

                # Получаем имя разными способами
                name = "Неизвестное имя"
                try:
                    # Способ 1: из атрибутов самого диалога
                    if hasattr(dialog, 'name') and dialog.name:
                        name = dialog.name
                    # Способ 2: из атрибутов entity
                    elif hasattr(entity, 'title') and entity.title:
                        name = entity.title
                    elif hasattr(entity, 'username') and entity.username:
                        name = f"@{entity.username}"
                    elif hasattr(entity, 'first_name') and entity.first_name:
                        name = entity.first_name
                        if hasattr(entity, 'last_name') and entity.last_name:
                            name += f" {entity.last_name}"
                except Exception as e:
                    logger.error(f"Ошибка получения имени: {str(e)}")
                    name = "Ошибка получения имени"

                # Определяем тип сущности
                if isinstance(entity, User):
                    entity_type = "Личный чат"
                elif dialog.is_group:
                    entity_type = "Группа"
                elif isinstance(entity, (Channel, PeerChannel)):
                    if getattr(entity, 'megagroup', False):
                        entity_type = "Супергруппа"
                    elif getattr(entity, 'broadcast', False):
                        entity_type = "Канал"
                    else:
                        entity_type = "Группа/Канал"
                elif isinstance(entity, PeerChat):
                    entity_type = "Группа"
                else:
                    entity_type = "Неизвестный тип"

                # Статус участия
                if getattr(entity, 'left', False):
                    status = " (Покинуто)"
                elif getattr(entity, 'kicked', False):
                    status = " (Заблокировано)"
                else:
                    status = " (Активно)"

                # Получаем ID
                entity_id = getattr(entity, 'id', 'N/A')
                # Чистка от непечатаемых символов (если нужно)
                name = name.encode('utf-8', 'ignore').decode('utf-8').strip()
                logger.info(f"Название: {name}")
                # Выводим сырое название без обработки
                logger.info("Сырое название: %s", {name})
                logger.info(f"Тип: {entity_type}{status}")
                logger.info(f"ID: {entity_id}")
                logger.info("------------------------")

            logger.info("=== Всего групп/каналов: %d ===", len(dialogs))

        except Exception as e:
            logger.error(f"Ошибка при получении списка подписок: {str(e)}", exc_info=True)

    async def load_group_keywords(self):
        """Загрузка групп и ключевых слов из БД с поддержкой ID"""
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

                    # Пытаемся определить, указан ли ID (число) или название
                    group_identifier = record.channel.strip()
                    keywords = {kw.strip().lower()
                                for kw in record.keywords.split(',')
                                if kw.strip()} if record.keywords else set()

                    # Сохраняем в формате {identifier: keywords}
                    self.group_keywords[group_identifier] = keywords
                    logger.info("Загружена группа: '%s' с ключевыми словами: %s",
                                group_identifier, keywords)

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
            logger.info(f"Всего диалогов: {len(dialogs)}")
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

                # Получаем количество участников
                participants_count = "N/A"
                try:
                    if hasattr(entity, 'participants_count'):
                        participants_count = entity.participants_count
                    else:
                        full_chat = await self.client.get_entity(entity)
                        if hasattr(full_chat, 'participants_count'):
                            participants_count = full_chat.participants_count
                except Exception as e:
                    logger.debug(
                        f"Не удалось получить количество участников: {str(e)}")

                # Получаем описание группы
                description = "Нет описания"
                try:
                    if hasattr(entity, 'about'):
                        description = entity.about if entity.about else "Нет описания"
                except Exception as e:
                    logger.debug(f"Не удалось получить описание: {str(e)}")

                # Получаем ссылку для приглашения
                invite_link = "N/A"
                try:
                    if hasattr(entity, 'username') and entity.username:
                        invite_link = f"https://t.me/{entity.username}"
                    else:
                        # Пытаемся получить экспортную ссылку
                        export_result = await self.client(
                            ExportChatInviteRequest(entity))
                        if export_result and hasattr(export_result, 'link'):
                            invite_link = export_result.link
                except Exception as e:
                    logger.debug(
                        f"Не удалось получить ссылку для приглашения: {str(e)}")

                logger.info("- Группа: '%s'%s", name, status)
                logger.info(f"  ID: {entity.id}")
                logger.info(f"  Тип: {type(entity)}")
                logger.info(f"  Участников: {participants_count}")
                logger.info(f"  Описание: {description}")
                logger.info(f"  Ссылка для приглашения: {invite_link}")
                logger.info("------------------------")

        except Exception as e:
            logger.error("Ошибка получения списка групп: %s", str(e),
                         exc_info=True)
    # ... (остальной код остается без изменений)

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

                # Получаем информацию о чате
                chat = await event.get_chat()
                if not chat:
                    logger.debug("Не удалось получить информацию о чате")
                    return

                # Получаем и название, и ID чата
                group_name = getattr(chat, 'title', None)
                group_id = str(chat.id) if hasattr(chat, 'id') else None

                logger.debug(f"Сообщение из чата: название='{group_name}', ID={group_id}")

                # Проверяем совпадение по названию или ID
                matched_identifier = None
                for identifier in self.group_keywords:
                    # Сравниваем с названием (если есть) или с ID
                    #logger.debug(f"Сравниваем с названием группы - {group_name}, ид группы - {group_id}")
                    if (group_name and identifier == group_name) or (group_id and identifier == group_id):
                        matched_identifier = identifier
                        break

                if not matched_identifier:
                    logger.debug(f"Чат не найден в БД (название='{group_name}', ID={group_id})")
                    return

                # Проверяем ключевые словосочетания
                keywords = self.group_keywords[matched_identifier]
                if not keywords:
                    logger.debug(f"Для чата '{matched_identifier}' нет ключевых слов")
                    return

                text_lower = message.text.lower()
                # Разделяем текст сообщения на слова и знаки препинания
                words = [word.strip() for word in text_lower.split()]

                # Проверяем каждое ключевое словосочетание
                for keyword_phrase in keywords:
                    # Разделяем ключевую фразу на слова
                    phrase_words = [w.strip() for w in keyword_phrase.split()]
                    if not phrase_words:
                        continue

                    # Ищем последовательное вхождение всех слов фразы в тексте
                    found = False
                    for i in range(len(words) - len(phrase_words) + 1):
                        if words[i:i + len(phrase_words)] == phrase_words:
                            found = True
                            break

                    if found:
                        display_name = group_name if group_name else f"ID:{group_id}"
                        logger.info(f"Найдено ключевое словосочетание '{keyword_phrase}' в чате '{display_name}'")
                        await self.forward_to_group(message, display_name)
                        break  # Прерываем после первого найденного совпадения

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

            # Выводим список всех групп и каналов пользователя
            await self.print_user_subscriptions()

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

async def logout():
  """Завершает сессию Telegram и удаляет файл сессии"""
  try:
    async with TelegramClient(TELEGRAM_SESSION_NAME, Config.TELEGRAM_API_SEND_BOOKING_ID,
                              Config.TELEGRAM_API_SEND_BOOKING_HASH) as client:
      await client.log_out()
      logger.info("Успешный выход из Telegram аккаунта")

    # Удаляем файл сессии
    session_file = Path(f"{TELEGRAM_SESSION_NAME}.session")
    if session_file.exists():
      session_file.unlink()
      logger.info(f"Файл сессии {session_file} удален")
  except Exception as e:
    logger.error(f"Ошибка при выходе из аккаунта: {str(e)}", exc_info=True)

if __name__ == "__main__":
    monitor = ChannelMonitor()
    monitor.run()
    #asyncio.run(logout())