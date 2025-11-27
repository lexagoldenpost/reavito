# send_tg_reklama.py
from typing import Optional, Union, List, Tuple
import asyncio

from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.telegram_client import telegram_client
from common.config import Config
from common.logging_config import setup_logger
from telega.telegram_utils import TelegramUtils

logger = setup_logger("send_tg_reklama")


class TelegramSender:
  """Обертка для обратной совместимости"""

  def __init__(self):
    self.client = telegram_client.client

  @property
  def phone(self):
    return Config.TELEGRAM_SEND_BOOKING_PHONE

  async def send_message_async(
      self,
      channel_identifier: Union[str, int],
      message: Optional[str] = None,
      media_files: Optional[Union[str, List[str]]] = None,
      return_message_link: bool = False
  ) -> Union[bool, Tuple[bool, str]]:
    """Асинхронная отправка сообщения в канал/группу"""
    # Логируем информацию об аккаунте
    try:
      await telegram_client.ensure_connection()
      me = await self.client.get_me()
      if me:
        username = f"@{me.username}" if me.username else "без username"
        logger.info(
          f"🆔 Отправка под аккаунтом: {me.first_name} {me.last_name or ''} "
          f"(ID: {me.id}, {username})")
    except Exception as e:
      logger.warning(f"Не удалось получить информацию об аккаунте: {e}")

    if media_files and isinstance(media_files, str):
      media_files = [media_files]

    return await telegram_client.send_message(
        channel_identifier, message, media_files, return_message_link
    )

  def send_message(
      self,
      channel_identifier: Union[str, int],
      message: Optional[str] = None,
      media_files: Optional[Union[str, List[str]]] = None,
      return_message_link: bool = False
  ) -> Union[bool, Tuple[bool, str]]:
    """Синхронная отправка сообщения в канал/группу"""
    if media_files and isinstance(media_files, str):
      media_files = [media_files]

    return asyncio.run(
        self.send_message_async(
            channel_identifier, message, media_files, return_message_link
        )
    )

  async def get_channel_info(self, channel_identifier: Union[str, int]):
    """Получить информацию о канале"""
    return await telegram_client.get_channel_info(channel_identifier)

  async def update_channels_csv_async(self) -> bool:
    """Асинхронное обновление CSV файлов"""
    return await telegram_client.update_channels_csv_async()

  def update_channels_csv(self) -> bool:
    """Синхронное обновление CSV файлов"""
    return telegram_client.update_channels_csv()


async def main():
  """Основная асинхронная функция для тестирования"""
  sender = TelegramSender()

  # Определяем путь к папке booking относительно корня проекта
  IMAGE_DATA_DIR = PROJECT_ROOT / "images" / "halo_title"

  # Пример: получение и логирование всех доступных каналов
  print("Получение списка всех доступных каналов...")
  async with sender.client:
      await TelegramUtils.initialize_client(sender.client, sender.phone)
      available_channels = await TelegramUtils.log_all_available_channels(sender.client)

      # Теперь вы можете использовать информацию из available_channels
      for channel in available_channels:
        if channel['can_send_messages']:
          print(
            f"Доступный канал для отправки: {channel['title']} (ID: {channel['id']})")

  # Пример 2: Текст с одним изображением и возвратом ссылки
  print("\nОтправка сообщения с изображением и возвратом ссылки:")
  result, message_link = await sender.send_message_async(
        -1002679682284,  # channel_identifier в числовом формате
        message="Сообщение с картинкой",
        media_files=[IMAGE_DATA_DIR / "photo_3.jpg"],
        return_message_link=True
    )
  print("Результат:", "Успешно" if result else "Ошибка")
  if result:
        print("Ссылка на сообщение:", message_link)

  # Пример 3: Несколько медиафайлов с возвратом ссылки
  print("\nОтправка нескольких медиафайлов с возвратом ссылки:")
  result, message_link = await sender.send_message_async(
        -1002679682284,  # channel_identifier в числовом формате
        media_files=[IMAGE_DATA_DIR / "photo_1.jpg", IMAGE_DATA_DIR / "photo_2.jpg"],
        return_message_link=True
    )
  print("Результат:", "Успешно" if result else "Ошибка")
  if result:
        print("Ссылка на сообщение:", message_link)

  # Пример 4: Обычная отправка без возврата ссылки (обратная совместимость)
  print("\nОбычная отправка без возврата ссылки:")
  result = await sender.send_message_async(
        -4612514156,
        message="Тестовое сообщение без возврата ссылки"
    )
  print("Результат:", "Успешно" if result else "Ошибка")

if __name__ == "__main__":
  import asyncio

  asyncio.run(main())