# send_tg_reklama.py
from pathlib import Path
from typing import Optional, Union, List

from telethon import TelegramClient, errors
from telethon.tl.types import InputMediaUploadedPhoto, InputMediaUploadedDocument
from telethon.sessions import StringSession

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.telegram_utils import TelegramUtils

logger = setup_logger("send_tg_reklama")


class TelegramSender:
    def __init__(self):
        self.api_id = Config.TELEGRAM_API_SEND_BOOKING_ID
        self.api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH
        self.phone = Config.TELEGRAM_SEND_BOOKING_PHONE

        # Определяем путь к файлу сессии
        session_filename = f"{self.api_id}_{Config.TELEGRAM_SESSION_NAME}"
        self.session_file_path = Path(f"{session_filename}.session")

        # Проверяем наличие файла сессии
        if self.session_file_path.exists():
            # Используем файл сессии
            session = str(self.session_file_path)
        else:
            # Пытаемся создать сессию через авторизацию
            session = str(self.session_file_path)  # Используем файловый путь для новой сессии

        self.client = TelegramClient(
            session,
            self.api_id,
            self.api_hash,
            system_version='4.16.30-vxCUSTOM',
            connection_retries=5,
            request_retries=3,
            auto_reconnect=True
        )

    async def _upload_media(self, file_path: str, caption: Optional[str] = None):
        """Загружает медиафайл на сервер Telegram"""
        try:
            file = Path(file_path)
            if not file.exists():
                logger.error(f"Файл не найден: {file_path}")
                return None

            if file.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                media = await self.client.upload_file(file)
                # Для фото caption передается отдельно при отправке
                return InputMediaUploadedPhoto(media)
            else:
                media = await self.client.upload_file(file)
                # Для документов caption также передается отдельно
                return InputMediaUploadedDocument(
                    media,
                    mime_type=None,
                    attributes=[],
                    # caption больше не передается здесь
                )
        except Exception as e:
            logger.error(f"Ошибка загрузки медиа: {str(e)}")
            return None

    async def _send_message_async(
            self,
            channel_identifier: Union[str, int],
            message: Optional[str] = None,
            media_files: Optional[List[str]] = None
    ):
        """Асинхронная отправка сообщения с медиа или без"""
        try:
            # Инициализируем клиент
            if not await TelegramUtils.initialize_client(self.client, self.phone):
                return False

            # Дополнительная отладка
            logger.info(f"Пытаемся разрешить идентификатор: {channel_identifier} (тип: {type(channel_identifier)})")

            # Разрешаем идентификатор канала
            result = await TelegramUtils.resolve_channel_identifier(self.client, channel_identifier)
            logger.info(f"Результат resolve_channel_identifier: {result}")
            if not result:
                logger.error(f"Не удалось разрешить идентификатор канала: {channel_identifier}")
                return False

            entity, channel_id, channel_name = result
            # Отображаем числовой ID в логах с пробелами как разделителями (реальный ID даже с минусом)
            channel_id_formatted = f"{channel_id:,}".replace(',', ' ')
            logger.info(f"Найден канал: {channel_name} (ID: {channel_id_formatted})")

            # Проверяем ограничения
            if not await TelegramUtils.check_account_restrictions(self.client, entity):
                logger.error(f"Аккаунт ограничен в {channel_name} (ID: {channel_id_formatted})")
                return False

            # Проверяем бан
            if await TelegramUtils.is_user_banned(self.client, entity.id):
                logger.error(f"Аккаунт забанен в {channel_name} (ID: {channel_id_formatted})")
                return False

            # Если есть медиафайлы
            if media_files:
                media_objects = []
                for file_path in media_files:
                    # Для первого медиафайла передаем caption, для остальных - None
                    media_caption = message if not media_objects else None
                    media = await self._upload_media(file_path)
                    if media:
                        media_objects.append(media)

                if not media_objects:
                    logger.error("Не удалось загрузить медиафайлы")
                    return False

                if len(media_objects) == 1:
                    # Для одного файла передаем caption как параметр
                    await self.client.send_message(entity, message=message, file=media_objects[0])
                else:
                    # Для альбома caption передается отдельно
                    await self.client.send_message(entity, message=message, file=media_objects)
            # Если только текст
            elif message:
                await self.client.send_message(entity, message)
            else:
                logger.error("Не указано ни сообщение, ни медиафайлы")
                return False

            logger.info(f"Сообщение успешно отправлено в {channel_name} (ID: {channel_id_formatted})")
            return True

        except errors.FloodWaitError as e:
            logger.error(f"Flood wait: нужно подождать {e.seconds} секунд")
            return False
        except errors.UserBannedInChannelError:
            logger.error(f"Аккаунт заблокирован в канале {channel_identifier}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {str(e)}")
            return False


    async def send_message_async(
            self,
            channel_identifier: Union[str, int],
            message: Optional[str] = None,
            media_files: Optional[Union[str, List[str]]] = None
    ) -> bool:
        """Асинхронная отправка сообщения в канал/группу"""
        # Нормализуем media_files в список
        if media_files and isinstance(media_files, str):
            media_files = [media_files]

        async with self.client:
            return await self._send_message_async(channel_identifier, message, media_files)

    async def get_channel_info(self, channel_identifier: Union[str, int]):
        """Получить информацию о канале"""
        async with self.client:
            try:
                if not await TelegramUtils.initialize_client(self.client, self.phone):
                    return None

                result = await TelegramUtils.resolve_channel_identifier(self.client, channel_identifier)
                if result:
                    entity, channel_id, channel_name = result
                    # Форматируем ID с пробелами как разделителями (реальный ID даже с минусом)
                    channel_id_formatted = f"{channel_id:,}".replace(',', ' ')
                    info = {
                        'entity': entity,
                        'id': channel_id,
                        'id_formatted': channel_id_formatted,
                        'name': channel_name,
                        'username': getattr(entity, 'username', None),
                        'title': getattr(entity, 'title', None),
                        'participants_count': getattr(entity, 'participants_count', None),
                        'accessible': await TelegramUtils.check_account_restrictions(self.client, entity),
                        'not_banned': not await TelegramUtils.is_user_banned(self.client, entity.id)
                    }
                    return info
                return None
            except Exception as e:
                logger.error(f"Ошибка получения информации о канале: {str(e)}")
                return None

    def send_message(
            self,
            channel_identifier: Union[str, int],
            message: Optional[str] = None,
            media_files: Optional[Union[str, List[str]]] = None
    ) -> bool:
        """Синхронная отправка сообщения в канал/группу"""
        if media_files and isinstance(media_files, str):
            media_files = [media_files]

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.send_message_async(channel_identifier, message, media_files)
        )

    async def update_channels_csv_async(self) -> bool:
      """Асинхронное обновление CSV файлов информацией о каналах"""
      async with self.client:
        try:
          if not await TelegramUtils.initialize_client(self.client, self.phone):
            return False

          await TelegramUtils.update_channels_csv_files_standalone(self.client)
          return True

        except Exception as e:
          logger.error(f"Ошибка при обновлении CSV файлов: {str(e)}")
          return False

    def update_channels_csv(self) -> bool:
      """Синхронное обновление CSV файлов информацией о каналах"""
      import asyncio
      try:
        loop = asyncio.get_event_loop()
      except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

      return loop.run_until_complete(self.update_channels_csv_async())


async def main():
    """Основная асинхронная функция"""
    sender = TelegramSender()

    # Определяем путь к папке booking относительно корня проекта
    IMAGE_DATA_DIR = PROJECT_ROOT / "images" / "halo_title"

    # Пример: получение и логирование всех доступных каналов
    print("Получение списка всех доступных каналов...")
    async with sender.client:
        await TelegramUtils.initialize_client(sender.client, sender.phone)
        available_channels = await TelegramUtils.log_all_available_channels(sender.client)

        # Теперь вы можете использовать информацию из available_channels
        # ВАЖНО: используйте реальный ID из поля 'id' (может быть отрицательным)
        for channel in available_channels:
            if channel['can_send_messages']:
                print(f"Доступный канал для отправки: {channel['title']} (ID: {channel['id']} , FULL_ID: {channel['full_id']})")

    # Пример 1: Только текст
    print("Отправка текстового сообщения:")
    result = await sender.send_message_async(
        -1002679682284,
        message="Тестовое текстовое сообщение"
    )
    print("Результат:", "Успешно" if result else "Ошибка")

    # Пример 2: Текст с одним изображением
    print("\nОтправка сообщения с изображением:")
    result = await sender.send_message_async(
        -1002679682284,  # channel_identifier в числовом формате
        message="Сообщение с картинкой",
        media_files= [IMAGE_DATA_DIR / "photo_3.jpg"]
    )
    print("Результат:", "Успешно" if result else "Ошибка")

    # Пример 3: Несколько медиафайлов
    print("\nОтправка нескольких медиафайлов:")
    result = await sender.send_message_async(
        -1002679682284,  # channel_identifier в числовом формате
        media_files=[IMAGE_DATA_DIR / "photo_1.jpg", IMAGE_DATA_DIR / "photo_2.jpg"]
    )
    print("Результат:", "Успешно" if result else "Ошибка")



# Обновленные примеры использования:
if __name__ == "__main__":
    import asyncio

    asyncio.run(main())