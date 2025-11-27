# scheduler/update_last_message_tg_info.py
from datetime import datetime
import csv
import os
import asyncio
from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.telegram_client import telegram_client
from telega.telegram_utils import TelegramUtils
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync

logger = setup_logger("update_last_message_tg_info")

# Определяем путь к папке booking относительно корня проекта
TASK_DATA_DIR = PROJECT_ROOT / Config.TASK_DATA_DIR


def load_chats_from_csv():
  """Загрузка данных о чатах из CSV файла"""
  chats = []
  csv_file = TASK_DATA_DIR / "channels.csv"

  if not os.path.exists(csv_file):
    logger.error(f"CSV file {csv_file} not found")
    return chats

  try:
    with open(csv_file, 'r', encoding='utf-8') as file:
      reader = csv.DictReader(file)

      # Получаем реальные названия колонок из заголовка
      fieldnames = reader.fieldnames
      logger.info(f"CSV fieldnames: {fieldnames}")

      for row in reader:
        try:
          last_send_str = row.get('Время последней отправки', '').strip()
          last_send = None
          if last_send_str:
            try:
              # Парсим дату из строки формата "YYYY-MM-DD HH:MM:SS"
              last_send = datetime.strptime(last_send_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
              try:
                # Парсим дату из строки формата "DD.MM.YYYY HH:MM:SS"
                last_send = datetime.strptime(last_send_str,
                                              "%d.%m.%Y %H:%M:%S")
              except ValueError:
                try:
                  # Парсим дату из строки формата "DD.MM.YYYY" (без времени)
                  last_send = datetime.strptime(last_send_str, "%d.%m.%Y")
                except ValueError:
                  logger.warning(
                    f"Could not parse last_send date: {last_send_str}")

          chat_data = {
            'chat_name': row['Наименование чата'].strip(),
            'send_frequency': int(
              row['Срок в днях меньше которого не отправляем'].strip()),
            'accepts_images': row[
                                'Картинки принимает (Да/Нет)'].strip().lower() == 'да',
            'channel_name': row['Название канала'].strip(),
            'chat_object': row.get('Объект чата', '').strip(),
            'last_send': last_send,
            'last_message_id': row.get('ИД последнего сообщения', '').strip(),
            'message_count_after_last': row.get(
              'Количество сообщение после последней публикации', '').strip(),
            '_sync_id': row['_sync_id'].strip()
          }
          chats.append(chat_data)
          logger.debug(
            f"Loaded chat: {chat_data['chat_name']}, last_send: {last_send}")

        except KeyError as e:
          logger.error(f"Missing column in CSV: {e}")
          continue
        except ValueError as e:
          logger.error(
            f"Error parsing data for chat {row.get('Наименование чата', 'unknown')}: {e}")
          continue

    logger.info(f"Loaded {len(chats)} chats from CSV")
  except Exception as e:
    logger.error(f"Error loading chats from CSV: {e}", exc_info=True)

  return chats


def save_chats_to_csv(chats):
  """Сохраняем обновленные данные в CSV"""
  try:
    csv_file = TASK_DATA_DIR / "channels.csv"

    # Читаем текущую структуру файла
    with open(csv_file, 'r', encoding='utf-8') as file:
      reader = csv.DictReader(file)
      fieldnames = reader.fieldnames

    # Обновляем данные
    updated_rows = []
    for chat in chats:
      # Форматируем дату в единый формат "YYYY-MM-DD HH:MM:SS"
      last_send_formatted = ''
      if chat['last_send']:
        last_send_formatted = chat['last_send'].strftime("%Y-%m-%d %H:%M:%S")

      row = {
        'Наименование чата': chat['chat_name'],
        'Срок в днях меньше которого не отправляем': str(
            chat['send_frequency']),
        'Картинки принимает (Да/Нет)': 'Да' if chat[
          'accepts_images'] else 'Нет',
        'Название канала': chat['channel_name'],
        'Время последней отправки': last_send_formatted,
        'Объект чата': chat.get('chat_object', ''),
        'ИД последнего сообщения': chat.get('last_message_id', ''),
        'Количество сообщение после последней публикации': chat.get(
          'message_count_after_last', ''),
        '_sync_id': chat['_sync_id']
      }
      updated_rows.append(row)

    # Записываем обратно
    with open(csv_file, 'w', encoding='utf-8', newline='') as file:
      writer = csv.DictWriter(file, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(updated_rows)

    logger.info(f"Successfully updated {len(chats)} chats in CSV")

    # Синхронизируем с Google Sheets
    sync_manager = GoogleSheetsCSVSync()
    sync_success = sync_manager.sync_sheet(
        sheet_name="Отправка бронирований",
        direction='csv_to_google'
    )

    if sync_success:
      logger.info("Successfully synchronized with Google Sheets")
    else:
      logger.error("Failed to synchronize with Google Sheets")

  except Exception as e:
    logger.error(f"Error saving chats to CSV: {e}")

async def get_last_message_id_difference(chat_name, stored_message_id):
  """
  Получаем разницу между последним сообщением в канале и сохраненным ID
  """
  try:
    if not stored_message_id:
      return None, "Нет данных"

    # Используем единого клиента
    if not await telegram_client.ensure_connection():
      return None, "Ошибка инициализации"

    # Получаем entity канала через утилиту
    result = await TelegramUtils.resolve_channel_identifier(
        telegram_client.client, chat_name
    )
    if not result:
      return None, "Канал не найден"

    entity, channel_id, channel_name = result

    # Получаем последнее сообщение через telethon
    messages = await telegram_client.client.get_messages(entity, limit=1)
    if not messages:
      return None, "Нет сообщений"

    last_message_id = messages[0].id

    try:
      stored_id = int(stored_message_id)
      difference = last_message_id - stored_id
      return last_message_id, difference
    except ValueError:
      return last_message_id, "Ошибка формата ID"

  except asyncio.TimeoutError:
    logger.error(f"Таймаут при получении ID сообщения для {chat_name}")
    return None, "Таймаут"
  except Exception as e:
    logger.error(f"Ошибка при получении ID сообщения для {chat_name}: {str(e)}")
    return None, f"Ошибка: {str(e)}"


async def process_chat_update(chat):
  """
  Обрабатывает обновление данных для одного канала
  """
  try:
    chat_name = chat['chat_name']
    stored_message_id = chat['last_message_id']

    logger.info(f"Processing chat: {chat_name}")

    # Получаем разницу ID сообщений
    last_message_id, difference = await get_last_message_id_difference(
        chat_name, stored_message_id
    )

    # Обновляем данные чата
    if isinstance(difference, int):
      chat['message_count_after_last'] = str(difference)
      logger.info(f"Updated {chat_name}: difference = {difference}")
    else:
      chat['message_count_after_last'] = difference
      logger.warning(f"Could not update {chat_name}: {difference}")

    return chat

  except Exception as e:
    logger.error(f"Error processing chat {chat['chat_name']}: {e}")
    return None


async def update_message_counts():
  """
  Основная функция для обновления счетчиков сообщений
  """
  logger.info("Starting update of message counts...")

  # Загружаем чаты из CSV
  all_chats = load_chats_from_csv()

  if not all_chats:
    logger.error("No chats loaded from CSV")
    return

  # Фильтруем чаты: у которых есть ИД последнего сообщения
  # и время последней публикации меньше 8 дней
  target_chats = []
  current_time = datetime.now()

  for chat in all_chats:
    # Проверяем наличие ID последнего сообщения
    if not chat.get('last_message_id'):
      continue

    # Проверяем время последней отправки (меньше 8 дней)
    last_send = chat.get('last_send')
    if last_send:
      days_diff = (current_time - last_send).days
      if days_diff < 8:
        target_chats.append(chat)
    else:
      # Если нет времени отправки, но есть ID сообщения - включаем
      target_chats.append(chat)

  logger.info(f"Found {len(target_chats)} chats to update")

  if not target_chats:
    logger.info("No chats meet the criteria for update")
    return

  # Создаем задачи для параллельной обработки
  tasks = []
  for chat in target_chats:
    tasks.append(process_chat_update(chat))

  # Выполняем все задачи параллельно с ограничением
  if tasks:
    semaphore = asyncio.Semaphore(3)  # Максимум 3 одновременных запроса

    async def bounded_task(task):
      async with semaphore:
        return await task

    bounded_tasks = [bounded_task(task) for task in tasks]
    results = await asyncio.gather(*bounded_tasks, return_exceptions=True)

    # Собираем обновленные чаты
    updated_chats = []
    for i, result in enumerate(results):
      if isinstance(result, Exception):
        logger.error(
          f"Ошибка при обработке канала {target_chats[i]['chat_name']}: {result}")
        # Сохраняем оригинальный чат в случае ошибки
        updated_chats.append(target_chats[i])
      elif result:
        updated_chats.append(result)
      else:
        # Сохраняем оригинальный чат если результат None
        updated_chats.append(target_chats[i])

    # Обновляем основной список чатов
    chat_dict = {chat['_sync_id']: chat for chat in all_chats}
    for updated_chat in updated_chats:
      chat_dict[updated_chat['_sync_id']] = updated_chat

    # Сохраняем все чаты обратно в CSV
    save_chats_to_csv(list(chat_dict.values()))

    logger.info("Message counts update completed successfully")

  else:
    logger.info("No tasks to process")


async def main():
  """
  Основная функция для запуска по расписанию
  """
  try:
    logger.info("Starting scheduled update of message counts...")

    # Инициализируем Telegram клиент
    if not await telegram_client.ensure_connection():
      logger.error("Failed to authenticate Telegram client")
      return

    # Выполняем обновление
    await update_message_counts()

    logger.info("Scheduled update completed successfully")

  except Exception as e:
    logger.error(f"Error in main scheduled task: {e}", exc_info=True)


if __name__ == "__main__":
  # Запуск напрямую (для тестирования)
  asyncio.run(main())