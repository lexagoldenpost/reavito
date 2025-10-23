# send_tg_reklama.py
from pathlib import Path
from typing import Optional, Union, List

from telethon import TelegramClient, errors
from telethon.tl.types import InputMediaUploadedPhoto, \
    InputMediaUploadedDocument

from common.config import Config
from common.logging_config import setup_logger

logger = setup_logger("telegram_sender")


class TelegramSender:
  def __init__(self):
    self.api_id = Config.TELEGRAM_API_SEND_BOOKING_ID
    self.api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH
    self.phone = Config.TELEGRAM_SEND_BOOKING_PHONE
    self.client = TelegramClient(
        'lapka_send_booking_session_name',
        self.api_id,
        self.api_hash,
        system_version='4.16.30-vxCUSTOM'
    )

  async def _check_account_restrictions(self, entity):
    """Проверяет ограничения аккаунта в канале/группе"""
    try:
      full_chat = await self.client.get_entity(entity)

      if hasattr(full_chat, 'participants_count'):
        participant = await self.client.get_participants(entity, limit=1)
        if not participant:
          logger.warning(f"Аккаунт не является участником {entity}")
          return False

      if hasattr(full_chat, 'default_banned_rights'):
        if full_chat.default_banned_rights.send_messages:
          logger.warning(f"Отправка сообщений запрещена в {entity}")
          return False
        if full_chat.default_banned_rights.send_media:
          logger.warning(f"Отправка медиа запрещена в {entity}")
          return False

      return True

    except errors.ChatWriteForbiddenError:
      logger.warning(f"Нет прав на отправку сообщений в {entity}")
      return False
    except errors.ChannelPrivateError:
      logger.warning(f"Аккаунт заблокирован в {entity}")
      return False
    except Exception as e:
      logger.error(f"Ошибка при проверке ограничений: {str(e)}")
      return False

  async def _upload_media(self, file_path: str, caption: Optional[str] = None):
    """Загружает медиафайл на сервер Telegram"""
    try:
      file = Path(file_path)
      if not file.exists():
        logger.error(f"Файл не найден: {file_path}")
        return None

      if file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
        media = await self.client.upload_file(file)
        return InputMediaUploadedPhoto(media, caption=caption)
      else:
        media = await self.client.upload_file(file)
        return InputMediaUploadedDocument(
            media,
            mime_type=None,
            attributes=[],
            caption=caption
        )
    except Exception as e:
      logger.error(f"Ошибка загрузки медиа: {str(e)}")
      return None

  async def _send_message_async(
      self,
      channel_name: str,
      message: Optional[str] = None,
      media_files: Optional[List[str]] = None
  ):
    """Асинхронная отправка сообщения с медиа или без"""
    try:
      await self.client.start(phone=self.phone)

      try:
        entity = await self.client.get_entity(channel_name)
      except ValueError:
        logger.error(f"Не удалось найти канал/чат {channel_name}")
        return False

      if not await self._check_account_restrictions(entity):
        logger.error(f"Аккаунт ограничен в {channel_name}")
        return False

      # Если есть медиафайлы
      if media_files:
        media_objects = []
        for file_path in media_files:
          media = await self._upload_media(file_path,
                                           message if not media_objects else None)
          if media:
            media_objects.append(media)

        if not media_objects:
          logger.error("Не удалось загрузить медиафайлы")
          return False

        if len(media_objects) == 1:
          await self.client.send_message(entity, file=media_objects[0])
        else:
          await self.client.send_message(entity, file=media_objects)
      # Если только текст
      elif message:
        await self.client.send_message(entity, message)
      else:
        logger.error("Не указано ни сообщение, ни медиафайлы")
        return False

      logger.info(f"Сообщение успешно отправлено в {channel_name}")
      return True

    except errors.FloodWaitError as e:
      logger.error(f"Flood wait: нужно подождать {e.seconds} секунд")
      return False
    except errors.UserBannedInChannelError:
      logger.error(f"Аккаунт заблокирован в канале {channel_name}")
      return False
    except Exception as e:
      logger.error(f"Ошибка при отправке сообщения: {str(e)}")
      return False
    finally:
      await self.client.disconnect()

  def send_message(
      self,
      channel_name: str,
      message: Optional[str] = None,
      media_files: Optional[Union[str, List[str]]] = None
  ) -> bool:
    """Отправляет сообщение в канал/группу

    Args:
        channel_name: Имя канала/группы (@"username" или "+79123456789")
        message: Текст сообщения (опционально, если отправляются медиафайлы)
        media_files: Путь к файлу или список путей к медиафайлам

    Returns:
        bool: True если сообщение отправлено успешно, False в случае ошибки
    """
    # Нормализуем media_files в список
    if media_files and isinstance(media_files, str):
      media_files = [media_files]

    with self.client:
      return self.client.loop.run_until_complete(
          self._send_message_async(channel_name, message, media_files)
      )


# Примеры использования:
if __name__ == "__main__":
  sender = TelegramSender()

  # Пример 1: Только текст
  print("Отправка текстового сообщения:")
  result = sender.send_message(
      channel_name="@LapkaAvitoBot",
      message="Тестовое текстовое сообщение"
  )
  print("Результат:", "Успешно" if result else "Ошибка")

  # Пример 2: Текст с одним изображением
  print("\nОтправка сообщения с изображением:")
  result = sender.send_message(
      channel_name="@LapkaAvitoBot",
      message="Сообщение с картинкой",
      media_files="test_image.jpg"
  )
  print("Результат:", "Успешно" if result else "Ошибка")

  # Пример 3: Несколько медиафайлов
  print("\nОтправка нескольких медиафайлов:")
  result = sender.send_message(
      channel_name="@LapkaAvitoBot",
      media_files=["image1.jpg", "document.pdf"]
  )
  print("Результат:", "Успешно" if result else "Ошибка")
  #sender.send_message("@channel", "Текст сообщения")
  #sender.send_message("@channel", "Описание", "image.jpg")
  #sender.send_message("@channel", media_files=["img1.jpg", "img2.png"])