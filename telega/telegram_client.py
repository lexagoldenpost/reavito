# telegram_client.py
from pathlib import Path
from typing import Optional, Union, List, Tuple, Dict
import asyncio

from telethon import TelegramClient
from telethon.tl.types import InputMediaUploadedPhoto, \
  InputMediaUploadedDocument
from telethon import errors

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.telegram_utils import TelegramUtils

logger = setup_logger("telegram_client")


class TelegramClientManager:
  """Единый менеджер для работы с Telegram API"""

  _instance = None
  _client = None

  def __new__(cls):
    if cls._instance is None:
      cls._instance = super().__new__(cls)
      cls._instance._initialize()
    return cls._instance

  def _initialize(self):
    """Инициализация клиента"""
    self.api_id = Config.TELEGRAM_API_SEND_BOOKING_ID
    self.api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH
    self.phone = Config.TELEGRAM_SEND_BOOKING_PHONE

    # Создаем папку sessions если её нет
    sessions_dir = PROJECT_ROOT / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    # Определяем путь к файлу сессии
    session_filename = f"{self.api_id}_{Config.TELEGRAM_SESSION_NAME}"
    self.session_file_path = sessions_dir / f"{session_filename}.session"

    # Создаем клиент
    self._client = TelegramClient(
        str(self.session_file_path),
        self.api_id,
        self.api_hash,
        system_version='4.16.30-vxCUSTOM',
        connection_retries=5,
        request_retries=3,
        auto_reconnect=True
    )

  @property
  def client(self) -> TelegramClient:
    """Получить экземпляр клиента"""
    return self._client

  async def ensure_authenticated(self) -> bool:
    """Убедиться, что клиент аутентифицирован"""
    return await TelegramUtils.initialize_client(self.client, self.phone)

  async def send_message(
      self,
      channel_identifier: Union[str, int],
      message: Optional[str] = None,
      media_files: Optional[List[str]] = None,
      return_message_link: bool = False
  ) -> Union[bool, Tuple[bool, str]]:
    """Отправка сообщения в канал/группу"""
    try:
      # Инициализируем клиент
      if not await self.ensure_authenticated():
        return (False, "") if return_message_link else False

      # Разрешаем идентификатор канала
      result = await TelegramUtils.resolve_channel_identifier(self.client,
                                                              channel_identifier)
      if not result:
        logger.error(
          f"Не удалось разрешить идентификатор канала: {channel_identifier}")
        return (False, "") if return_message_link else False

      entity, channel_id, channel_name = result

      # Проверяем ограничения
      if not await TelegramUtils.check_account_restrictions(self.client,
                                                            entity):
        logger.error(f"Аккаунт ограничен в {channel_name}")
        return (False, "") if return_message_link else False

      # Проверяем бан
      if await TelegramUtils.is_user_banned(self.client, entity.id):
        logger.error(f"Аккаунт забанен в {channel_name}")
        return (False, "") if return_message_link else False

      # Отправка сообщения
      sent_message = None
      message_link = ""

      if media_files:
        # Логика отправки медиа
        media_objects = []
        for file_path in media_files:
          media_caption = message if not media_objects else None
          media = await self._upload_media(file_path)
          if media:
            media_objects.append(media)

        if not media_objects:
          logger.error("Не удалось загрузить медиафайлы")
          return (False, "") if return_message_link else False

        if len(media_objects) == 1:
          sent_message = await self.client.send_message(
              entity, message=message, file=media_objects[0]
          )
        else:
          sent_message = await self.client.send_message(
              entity, message=message, file=media_objects
          )
      elif message:
        sent_message = await self.client.send_message(entity, message)
      else:
        logger.error("Не указано ни сообщение, ни медиафайлы")
        return (False, "") if return_message_link else False

      # Генерация ссылки на сообщение
      if return_message_link and sent_message:
        if isinstance(sent_message, list) and sent_message:
          message_link = await TelegramUtils.get_message_link(
              self.client, entity, sent_message[0].id
          )
        elif sent_message:
          message_link = await TelegramUtils.get_message_link(
              self.client, entity, sent_message.id
          )
        return True, message_link
      else:
        return True

    except errors.FloodWaitError as e:
      logger.error(f"Flood wait: нужно подождать {e.seconds} секунд")
      return (False, "") if return_message_link else False
    except Exception as e:
      logger.error(f"Ошибка при отправке сообщения: {str(e)}")
      return (False, "") if return_message_link else False

  async def _upload_media(self, file_path: str):
    """Загружает медиафайл на сервер Telegram"""
    try:
      file = Path(file_path)
      if not file.exists():
        logger.error(f"Файл не найден: {file_path}")
        return None

      if file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
        media = await self.client.upload_file(file)
        return InputMediaUploadedPhoto(media)
      else:
        media = await self.client.upload_file(file)
        return InputMediaUploadedDocument(
            media, mime_type=None, attributes=[]
        )
    except Exception as e:
      logger.error(f"Ошибка загрузки медиа: {str(e)}")
      return None

  async def get_channel_info(self, channel_identifier: Union[str, int]) -> \
  Optional[Dict]:
    """Получить информацию о канале"""
    try:
      if not await self.ensure_authenticated():
        return None

      result = await TelegramUtils.resolve_channel_identifier(self.client,
                                                              channel_identifier)
      if result:
        entity, channel_id, channel_name = result
        info = {
          'entity': entity,
          'id': channel_id,
          'name': channel_name,
          'username': getattr(entity, 'username', None),
          'title': getattr(entity, 'title', None),
          'participants_count': getattr(entity, 'participants_count', None),
          'accessible': await TelegramUtils.check_account_restrictions(
            self.client, entity),
          'not_banned': not await TelegramUtils.is_user_banned(self.client,
                                                               entity.id)
        }
        return info
      return None
    except Exception as e:
      logger.error(f"Ошибка получения информации о канале: {str(e)}")
      return None

  async def update_channels_csv_async(self) -> bool:
    """Асинхронное обновление CSV файлов информацией о каналах"""
    try:
      if not await self.ensure_authenticated():
        return False

      await TelegramUtils.update_channels_csv_files_standalone(self.client)
      return True

    except Exception as e:
      logger.error(f"Ошибка при обновлении CSV файлов: {str(e)}")
      return False

  def update_channels_csv(self) -> bool:
    """Синхронное обновление CSV файлов информацией о каналах"""
    try:
      loop = asyncio.get_event_loop()
    except RuntimeError:
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)

    return loop.run_until_complete(self.update_channels_csv_async())


# Синглтон экземпляр
telegram_client = TelegramClientManager()