# telegram_utils.py
from typing import Optional, List, Tuple, Union
from pathlib import Path
import logging
from telethon import TelegramClient
from telethon.tl.types import ChatBannedRights, Channel, User, PeerChannel, Chat
from telethon.errors import ChatWriteForbiddenError, ChannelPrivateError, UsernameNotOccupiedError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.channels import GetChannelsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.tl.functions.users import GetFullUserRequest
from common.logging_config import setup_logger
from common.config import Config

logger = setup_logger("telegram_utils")


class TelegramUtils:
    """Утилиты для работы с Telegram"""

    @staticmethod
    async def check_account_restrictions(client: TelegramClient, entity) -> bool:
        """Проверяет ограничения аккаунта в канале/группе"""
        try:
            # Проверяем права на отправку через атрибуты entity
            if hasattr(entity, 'default_banned_rights') and entity.default_banned_rights:
                if hasattr(entity.default_banned_rights, 'send_messages'):
                    if entity.default_banned_rights.send_messages:
                        logger.warning(f"Отправка сообщений запрещена в {getattr(entity, 'title', 'N/A')}")
                        return False
                if hasattr(entity.default_banned_rights, 'send_media'):
                    if entity.default_banned_rights.send_media:
                        logger.warning(f"Отправка медиа запрещена в {getattr(entity, 'title', 'N/A')}")
                        return False

            return True

        except ChatWriteForbiddenError:
            logger.warning(f"Нет прав на отправку сообщений в {getattr(entity, 'title', 'N/A')}")
            return False
        except ChannelPrivateError:
            logger.warning(f"Аккаунт заблокирован в {getattr(entity, 'title', 'N/A')}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке ограничений: {str(e)}")
            return False

    @staticmethod
    async def is_user_banned(client: TelegramClient, chat_id: int) -> bool:
        """Проверяет, забанен ли пользователь в чате"""
        try:
            chat = await client.get_entity(chat_id)
            if isinstance(chat, Channel):
                try:
                    participant = await client.get_permissions(chat, 'me')
                    if hasattr(participant, 'banned_rights') and participant.banned_rights:
                        if isinstance(participant.banned_rights, ChatBannedRights):
                            return participant.banned_rights.view_messages
                    elif hasattr(participant, 'kicked'):
                        return participant.kicked
                except Exception:
                    # Если не можем получить права участника, проверяем другие атрибуты
                    if hasattr(chat, 'banned_rights') and chat.banned_rights:
                        if isinstance(chat.banned_rights, ChatBannedRights):
                            return chat.banned_rights.view_messages
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки бана в чате {chat_id}: {e}")
            return False

    @staticmethod
    async def get_entity_safe(client: TelegramClient, identifier: Union[str, int]):
        """Безопасное получение entity с обработкой ошибок"""
        try:
            return await client.get_entity(identifier)
        except ValueError as e:
            logger.error(f"Не удалось найти канал/чат {identifier}: {e}")
            return None
        except UsernameNotOccupiedError:
            logger.error(f"Username {identifier} не существует или не занят")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения entity {identifier}: {str(e)}")
            return None

    @staticmethod
    def _get_verification_code():
        """Получить код верификации от пользователя"""
        return input("Enter SMS/Telegram verification code: ")

    @staticmethod
    async def initialize_client(client: TelegramClient, phone: str) -> bool:
        """Инициализация клиента Telegram"""
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.info("No valid session found. Starting new authorization...")
                await client.start(
                    phone=phone,
                    password=getattr(Config, 'TELEGRAM_PASSWORD', None),
                    code_callback=TelegramUtils._get_verification_code
                )
                # После успешной авторизации выводим новую строку сессии
                new_session_str = client.session.save()
                logger.critical("✅ NEW STRING SESSION (SAVE THIS IMMEDIATELY):")
                logger.critical(new_session_str)
                return True
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации клиента: {str(e)}")
            return False

    @staticmethod
    async def resolve_channel_identifier(client: TelegramClient, identifier: str) -> Optional[Tuple]:
        """Разрешает идентификатор канала в entity и ID"""
        try:
            # Пробуем получить entity
            entity = await TelegramUtils.get_entity_safe(client, identifier)
            if not entity:
                return None

            # Получаем ID канала
            if hasattr(entity, 'id'):
                channel_id = entity.id
                # Для каналов ID обычно отрицательный, преобразуем в строку для удобства
                if channel_id < 0:
                    # Преобразуем в формат -100XXXXXXX
                    full_channel_id = f"-100{abs(channel_id)}"
                else:
                    full_channel_id = str(channel_id)

                # Получаем имя канала
                channel_name = getattr(entity, 'title', None) or getattr(entity, 'username', None) or str(identifier)

                return entity, full_channel_id, channel_name

            return None

        except Exception as e:
            logger.error(f"Ошибка разрешения идентификатора {identifier}: {str(e)}")
            return None

    @staticmethod
    async def get_current_user_info(client: TelegramClient) -> Optional[dict]:
        """
        Получает информацию о текущем пользователе
        """
        try:
            me = await client.get_me()
            if me:
                # Получаем полную информацию о пользователе
                full_user = await client(GetFullUserRequest(me))

                user_info = {
                    'id': me.id,
                    'first_name': getattr(me, 'first_name', 'N/A'),
                    'last_name': getattr(me, 'last_name', None),
                    'username': getattr(me, 'username', None),
                    'phone': getattr(me, 'phone', None),
                    'bot': getattr(me, 'bot', False),
                    'premium': getattr(full_user, 'premium', False),
                    'verified': getattr(me, 'verified', False),
                    'scam': getattr(me, 'scam', False),
                    'fake': getattr(me, 'fake', False),
                    'full_name': f"{me.first_name} {me.last_name}" if me.last_name else me.first_name,
                    'link': f"https://t.me/{me.username}" if me.username else 'N/A'
                }
                return user_info
            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе: {str(e)}")
            return None

    @staticmethod
    async def get_all_available_channels(client: TelegramClient) -> List[dict]:
        """
        Получает все доступные каналы, группы и чаты, в которых состоит аккаунт
        """
        try:
            # Получаем все диалоги (чаты, группы, каналы)
            dialogs = await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=1000,  # Максимум 1000 диалогов
                hash=0
            ))

            available_channels = []

            for dialog in dialogs.dialogs:
                try:
                    entity = await client.get_entity(dialog.peer)

                    # Проверяем, является ли это каналом или группой
                    if isinstance(entity, (Channel, Chat)):
                        # Проверяем права доступа
                        is_accessible = await TelegramUtils.check_account_restrictions(client, entity)
                        is_not_banned = not await TelegramUtils.is_user_banned(client, entity.id)

                        # Формируем информацию о канале
                        channel_info = {
                            'entity': entity,
                            'id': entity.id,
                            'full_id': f"-100{abs(entity.id)}" if entity.id < 0 else str(entity.id),
                            'title': getattr(entity, 'title', 'N/A'),
                            'username': getattr(entity, 'username', None),
                            'link': f"https://t.me/{entity.username}" if getattr(entity, 'username', None) else 'N/A',
                            'type': 'Channel' if isinstance(entity, Channel) else 'Group',
                            'participants_count': getattr(entity, 'participants_count', None),
                            'description': getattr(entity, 'about', 'N/A'),
                            'accessible': is_accessible,
                            'not_banned': is_not_banned,
                            'can_send_messages': is_accessible and is_not_banned,
                            'date': getattr(dialog, 'date', None),
                            'is_muted': getattr(dialog.notify_settings, 'mute_until', None) is not None,
                            'is_archived': getattr(dialog, 'folder_id', None) == 1
                        }

                        available_channels.append(channel_info)

                except Exception as e:
                    logger.error(f"Ошибка при обработке диалога: {str(e)}")
                    continue

            return available_channels

        except Exception as e:
            logger.error(f"Ошибка получения списка каналов: {str(e)}")
            return []

    @staticmethod
    async def log_all_available_channels(client: TelegramClient) -> List[dict]:
        """
        Выводит в лог все доступные каналы с полной информацией в одну строку
        """
        # Сначала получаем информацию о текущем пользователе
        user_info = await TelegramUtils.get_current_user_info(client)

        if user_info:
            logger.info(f"=== ИНФОРМАЦИЯ О ТЕКУЩЕМ ПОЛЬЗОВАТЕЛЕ ===")
            logger.info(f"Пользователь: {user_info['full_name']} (ID: {user_info['id']})")
            logger.info(f"Username: @{user_info['username']}" if user_info['username'] else f"Username: N/A")
            logger.info(f"Телефон: {user_info['phone']}")
            logger.info(f"Ссылка: {user_info['link']}")
            logger.info(f"Бот: {'Да' if user_info['bot'] else 'Нет'}")
            logger.info(f"Premium: {'Да' if user_info['premium'] else 'Нет'}")
            logger.info(f"Верифицирован: {'Да' if user_info['verified'] else 'Нет'}")
            logger.info(f"Скам: {'Да' if user_info['scam'] else 'Нет'}")
            logger.info(f"Фейк: {'Да' if user_info['fake'] else 'Нет'}")
            logger.info("==========================================")

        logger.info("=== НАЧАЛО СПИСКА ДОСТУПНЫХ КАНАЛОВ И ГРУПП ===")

        channels = await TelegramUtils.get_all_available_channels(client)

        if not channels:
            logger.info("Не найдено доступных каналов или групп")
            return []

        logger.info(f"Найдено {len(channels)} каналов/групп:")

        for i, channel in enumerate(channels, 1):
            logger.info(
                f"Канал #{i}: Название='{channel['title']}', Тип='{channel['type']}', ID={channel['id']}, Полный_ID='{channel['full_id']}', Username='{channel['username']}', Ссылка='{channel['link']}', Участников={channel['participants_count']}, Доступен={'Да' if channel['accessible'] else 'Нет'}, Не_забанен={'Да' if channel['not_banned'] else 'Нет'}, Можно_отправлять={'Да' if channel['can_send_messages'] else 'Нет'}, Заглушен={'Да' if channel['is_muted'] else 'Нет'}, Архив={'Да' if channel['is_archived'] else 'Нет'}")

        logger.info("=== КОНЕЦ СПИСКА ДОСТУПНЫХ КАНАЛОВ ===")

        return channels