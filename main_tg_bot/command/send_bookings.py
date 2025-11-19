# send_bookings.py
from datetime import datetime, timedelta
import csv
import os
import asyncio
import aiohttp

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT, get_all_booking_files
from telega.telegram_client import telegram_client
from telega.telegram_utils import TelegramUtils
from telega.tg_notifier import send_message as send_telegram_message
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync

logger = setup_logger("send_bookings")

# Добавляем префиксы для callback-данных
CALLBACK_PREFIX = "sb_"  # sb = send_bookings
SELECT_OBJECT = f"{CALLBACK_PREFIX}select_object"
SEND_BROADCAST = f"{CALLBACK_PREFIX}send_broadcast"
REFRESH_CHATS = f"{CALLBACK_PREFIX}refresh"
BACK_TO_OBJECTS = f"{CALLBACK_PREFIX}back_to_objects"

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
              # Парсим дату из строки формата "YYYY-MM-DD HH:MM:SS" или "DD.MM.YYYY"
              last_send = datetime.strptime(last_send_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
              try:
                last_send = datetime.strptime(last_send_str,
                                              "%d.%m.%Y %H:%M:%S")
              except ValueError:
                logger.warning(
                    f"Could not parse last_send date: {last_send_str}")

          chat_data = {
            'chat_name': row['Наименование чата'].strip(),
            'send_frequency': int(
                row['Срок в днях меньше которого не отправляем '].strip()),
            'accepts_images': row[
                                'Картинки принимает (Да/Нет)'].strip().lower() == 'да',
            'channel_name': row['Название канала'].strip(),
            'chat_object': row.get('Объект чата', '').strip(),
            'last_send': last_send,
            'last_message_id': row.get('ID отправленного сообщения',
                                       '').strip(),
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


def save_send_result(chat_name, message_id, message_link):
  """Сохраняем результат отправки в CSV"""
  try:
    csv_file = TASK_DATA_DIR / "channels.csv"

    # Читаем все данные
    with open(csv_file, 'r', encoding='utf-8') as file:
      reader = csv.DictReader(file)
      rows = list(reader)
      fieldnames = reader.fieldnames

    # Обновляем время и ID сообщения для конкретного чата
    for row in rows:
      if row['Наименование чата'].strip() == chat_name:
        row['Время последней отправки'] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")
        row['ID отправленного сообщения'] = str(message_id)
        break

    # Записываем обратно
    with open(csv_file, 'w', encoding='utf-8', newline='') as file:
      writer = csv.DictWriter(file, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(rows)

    logger.debug(f"Saved send result for {chat_name}: message_id={message_id}")

    # Обновляем в гугл таблице
    sync_manager = GoogleSheetsCSVSync()
    sync_success = sync_manager.sync_sheet(sheet_name="Отправка бронирований",
                                           direction='csv_to_google')
    if not sync_success:
      raise RuntimeError("Синхронизация завершилась со статусом False")

  except Exception as e:
    logger.error(f"Error saving send result to CSV: {e}")


async def get_last_message_id_difference(chat_name, stored_message_id):
  """
  Получаем разницу между последним сообщением в канале и сохраненным ID
  Используем единого клиента
  """
  try:
    if not stored_message_id:
      return None, "Нет данных"

    # Используем единого клиента
    if not await telegram_client.ensure_authenticated():
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
      return last_message_id, f"{difference:+d}"
    except ValueError:
      return last_message_id, "Ошибка формата ID"

  except asyncio.TimeoutError:
    logger.error(f"Таймаут при получении ID сообщения для {chat_name}")
    return None, "Таймаут"
  except Exception as e:
    logger.error(f"Ошибка при получении ID сообщения для {chat_name}: {str(e)}")
    return None, f"Ошибка: {str(e)}"


async def check_recent_messages(chat_id, my_user_id):
  """
  Проверяем, есть ли наши сообщения в последних 8 сообщениях чата
  Используем единого клиента
  """
  try:
    # Используем единого клиента
    if not await telegram_client.ensure_authenticated():
      return False

    # Получаем entity канала через утилиту
    result = await TelegramUtils.resolve_channel_identifier(
        telegram_client.client, chat_id
    )
    if not result:
      return False

    entity, channel_id, channel_name = result

    # Получаем последние 8 сообщений через telethon
    messages = await telegram_client.client.get_messages(entity, limit=8)

    # Проверяем, есть ли среди них наши сообщения
    for message in messages:
      if hasattr(message, 'from_id') and message.from_id:
        # Сравниваем ID отправителя
        sender_id = getattr(message.from_id, 'user_id', None)
        if sender_id == my_user_id:
          logger.info(
              f"Найдено наше сообщение в последних 8 сообщениях канала {channel_name}")
          return False

    return True

  except asyncio.TimeoutError:
    logger.error(f"Таймаут при проверке сообщений в {chat_id}")
    return True  # В случае таймаута разрешаем отправку
  except Exception as e:
    logger.error(
      f"Ошибка при проверке последних сообщений в {chat_id}: {str(e)}")
    return True  # В случае ошибки разрешаем отправку


async def get_current_user_id():
  """
  Получаем ID текущего пользователя один раз с таймаутом
  Используем единого клиента
  """
  try:
    if not await telegram_client.ensure_authenticated():
      return None

    user_info = await TelegramUtils.get_current_user_info(telegram_client.client)
    return user_info['id'] if user_info else None

  except asyncio.TimeoutError:
    logger.error("Таймаут при получении ID пользователя")
    return None
  except Exception as e:
    logger.error(f"Ошибка при получении ID пользователя: {e}")
    return None


async def get_available_dates_for_object(object_name):
  """
  Заглушка для получения свободных дат объекта
  В будущем можно интегрировать с реальными данными о бронированиях
  """
  # Заглушка - возвращаем фиктивные даты
  current_date = datetime.now()
  available_dates = []

  for i in range(3, 10):  # Следующие 7 дней начиная с 3-го дня
    date = current_date + timedelta(days=i)
    if date.weekday() < 5:  # Только будние дни
      available_dates.append(date.strftime("%d.%m.%Y"))

  return available_dates


async def get_available_chats_for_object(target_object=None):
  """Получаем доступные чаты для конкретного объекта"""
  current_date = datetime.now()
  all_chats = load_chats_from_csv()
  available_chats = []

  # Получаем ID пользователя один раз для всех проверок
  my_user_id = await get_current_user_id()

  # Создаем задачи для параллельной обработки каналов
  tasks = []
  for chat in all_chats:
    # Проверяем принадлежность к объекту
    chat_object = chat['chat_object']
    if target_object and target_object != 'all':
      if not chat_object or chat_object != target_object:
        continue
    elif target_object == 'all':
      # Для "Все объекты" включаем все чаты без фильтрации по объекту
      pass
    else:
      # Для общего списка не включаем чаты с указанным объектом
      if chat_object:
        continue

    # Проверяем время последней отправки (дни + 5 минут)
    last_send = chat['last_send']
    can_send_by_time = True

    if last_send:
      # Добавляем 5 минут к частоте отправки
      next_send_time = last_send + timedelta(days=chat['send_frequency'],
                                             minutes=5)
      can_send_by_time = current_date >= next_send_time

    if can_send_by_time:
      # Добавляем задачу для проверки сообщений и получения ID
      tasks.append(process_chat_data(chat, my_user_id))

  # Выполняем все задачи параллельно с ограничением
  if tasks:
    semaphore = asyncio.Semaphore(5)  # Максимум 5 одновременных проверок

    async def bounded_task(task):
      async with semaphore:
        return await task

    bounded_tasks = [bounded_task(task) for task in tasks]
    results = await asyncio.gather(*bounded_tasks, return_exceptions=True)

    # Обрабатываем результаты
    for result in results:
      if isinstance(result, Exception):
        logger.error(f"Ошибка при обработке канала: {result}")
      elif result:  # Если канал доступен
        available_chats.append(result)

  return available_chats


async def process_chat_data(chat, my_user_id):
  """
  Обрабатывает данные одного канала: проверяет сообщения и получает разницу ID
  """
  try:
    # Проверяем последние сообщения
    can_send_by_messages = True
    if my_user_id:
      can_send_by_messages = await check_recent_messages(chat['chat_name'],
                                                         my_user_id)

    # Получаем разницу ID сообщений
    last_message_id, id_difference = await get_last_message_id_difference(
        chat['chat_name'], chat['last_message_id']
    )

    chat['last_message_id_info'] = {
      'current_id': last_message_id,
      'difference': id_difference
    }

    if can_send_by_messages:
      return chat
    return None

  except Exception as e:
    logger.error(f"Ошибка при обработке канала {chat['chat_name']}: {e}")
    return None


async def send_bookings_handler(update, context):
  """Обработчик для рассылки бронирований"""
  logger.info("Entered send_bookings_handler")
  try:
    if update.callback_query:
      logger.debug(f"Received callback query: {update.callback_query.data}")
      # Проверяем, что callback относится к этому модулю
      if update.callback_query.data.startswith(CALLBACK_PREFIX):
        logger.debug("Callback belongs to this module, processing...")
        return await handle_callback(update, context)
      else:
        logger.debug("Callback not for this module, skipping...")
        return
    elif update.message:
      logger.debug(f"Received message: {update.message.text}")
      return await handle_message(update, context)
    else:
      logger.error("Unknown update type in send_bookings_handler")

  except Exception as e:
    logger.error(f"Error in send_bookings_handler: {e}", exc_info=True)
    error_message = "Произошла ошибка при обработке запроса"
    await send_reply(update, error_message)


async def handle_message(update, context):
  """Обработка текстовых сообщений - всегда начинаем заново"""
  if update.message.text.strip().lower() == '/exit':
    await send_reply(update, "Сессия завершена. Начните заново.")
    # Очищаем данные пользователя
    if 'selected_object' in context.user_data:
      del context.user_data['selected_object']
    return

  # Всегда начинаем с выбора объекта
  await show_objects_selection(update, context)


async def handle_callback(update, context):
  """Обработка нажатия на кнопку"""
  logger.info("Entered handle_callback")
  query = update.callback_query
  await query.answer()
  logger.debug(f"Callback query answered: {query.data}")

  try:
    if query.data.startswith(SELECT_OBJECT):
      # Выбор объекта
      parts = query.data.split('_')
      if len(parts) >= 3:
        object_name = '_'.join(parts[3:])
        await show_object_channels(update, context, object_name)

    elif query.data == SEND_BROADCAST:
      # Запуск рассылки
      if 'selected_object' in context.user_data:
        await start_broadcast(update, context,
                              context.user_data['selected_object'])
      else:
        await send_reply(update, "❌ Ошибка: объект не выбран")

    elif query.data == BACK_TO_OBJECTS:
      # Возврат к выбору объекта
      await show_objects_selection(update, context)

    elif query.data == REFRESH_CHATS:
      # Обновление списка
      if 'selected_object' in context.user_data:
        await show_object_channels(update, context,
                                   context.user_data['selected_object'])
      else:
        await show_objects_selection(update, context)

    else:
      logger.debug(f"Ignoring callback with data: {query.data}")
      return

  except Exception as e:
    logger.error(f"Error in handle_callback: {e}", exc_info=True)
    await send_reply(update, "❌ Ошибка. Используйте /exit для сброса.")


async def show_objects_selection(update, context):
  """Показать выбор объектов (аналогично view_booking)"""
  logger.info("Entered show_objects_selection")
  try:
    # Очищаем предыдущие данные
    if 'selected_object' in context.user_data:
      del context.user_data['selected_object']

    # Получаем объекты из booking_objects
    objects_data = get_all_booking_files()

    # Получаем доступные объекты из SHEET_TO_FILENAME
    from main_tg_bot.booking_objects import SHEET_TO_FILENAME

    keyboard = []

    # Добавляем объекты
    for obj_name, filename in SHEET_TO_FILENAME.items():
      # Получаем количество доступных каналов для этого объекта
      available_chats = await get_available_chats_for_object(obj_name)
      count = len(available_chats)

      button_text = f"{obj_name} ({count} каналов)"
      callback_data = f"{SELECT_OBJECT}_{obj_name}"

      keyboard.append(
          [InlineKeyboardButton(button_text, callback_data=callback_data)])

    # Добавляем кнопку "Все объекты" (чаты без указанного объекта)
    all_chats = await get_available_chats_for_object('all')
    count_all = len(all_chats)
    keyboard.append([InlineKeyboardButton(f"Все объекты ({count_all} каналов)",
                                          callback_data=f"{SELECT_OBJECT}_all")])

    refresh_button = InlineKeyboardButton("🔄 Обновить список",
                                          callback_data=REFRESH_CHATS)
    keyboard.append([refresh_button])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_reply(
        update,
        "🏢 Выберите объект для рассылки:",
        reply_markup=reply_markup
    )

  except asyncio.CancelledError:
    logger.info("Операция отменена пользователем")
    raise
  except Exception as e:
    logger.error(f"Error in show_objects_selection: {e}", exc_info=True)
    await send_reply(update, "❌ Ошибка при загрузке объектов \nВыход /exit")


async def show_object_channels(update, context, object_name):
  """Показать каналы для выбранного объекта с детальной информацией"""
  logger.info(f"Entered show_object_channels for {object_name}")
  try:
    # Сохраняем выбранный объект в контексте
    context.user_data['selected_object'] = object_name

    # Получаем доступные объекты из SHEET_TO_FILENAME
    from main_tg_bot.booking_objects import SHEET_TO_FILENAME

    if object_name == 'all':
      display_name = "Все объекты"
      available_chats = await get_available_chats_for_object('all')
    else:
      display_name = object_name  # Используем имя объекта напрямую
      available_chats = await get_available_chats_for_object(object_name)

    # Получаем свободные даты (заглушка)
    available_dates = await get_available_dates_for_object(object_name)

    # Формируем сообщение с информацией
    message_text = f"🏢 **{display_name}**\n\n"

    # Свободные даты
    message_text += "📅 **Свободные даты:**\n"
    if available_dates:
      for i, date in enumerate(available_dates[:5],
                               1):  # Показываем первые 5 дат
        message_text += f"{i}. {date}\n"
      if len(available_dates) > 5:
        message_text += f"... и еще {len(available_dates) - 5} дат\n"
    else:
      message_text += "❌ Нет свободных дат\n"

    message_text += f"\n📊 **Доступно каналов:** {len(available_chats)}\n\n"

    # Добавляем список каналов с детальной информацией
    if available_chats:
      message_text += "📢 **Доступные каналы:**\n"
      for i, chat in enumerate(available_chats, 1):
        chat_display = chat['channel_name'] or chat['chat_name']
        last_send = chat['last_send']
        last_send_str = last_send.strftime(
          "%d.%m.%Y %H:%M") if last_send else "Никогда"

        # Информация о разнице ID сообщений
        id_info = chat.get('last_message_id_info', {})
        id_difference = id_info.get('difference', 'Нет данных')

        message_text += f"\n**{i}. {chat_display}**\n"
        message_text += f"   📅 Последняя отправка: {last_send_str}\n"
        message_text += f"   🔢 Разница ID: {id_difference}\n"
    else:
      message_text += "❌ Нет доступных каналов для рассылки\n"

    # Создаем клавиатуру
    keyboard = []
    if available_chats:
      keyboard.append([InlineKeyboardButton("🚀 Начать рассылку",
                                            callback_data=SEND_BROADCAST)])

    keyboard.append([InlineKeyboardButton("⬅️ Назад к объектам",
                                          callback_data=BACK_TO_OBJECTS)])
    keyboard.append(
        [InlineKeyboardButton("🔄 Обновить", callback_data=REFRESH_CHATS)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_reply(
        update,
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

  except asyncio.CancelledError:
    logger.info("Операция отменена пользователем")
    raise
  except Exception as e:
    logger.error(f"Error in show_object_channels: {e}", exc_info=True)
    await send_reply(update,
                     "❌ Ошибка при загрузке каналов объекта \nВыход /exit")


async def send_broadcast_to_chat(sender, chat, object_display_name, update):
  """Отправка сообщения в один канал и возврат результата"""
  try:
    # Формируем сообщение
    message_text = f"🏢 {object_display_name}\n\n"
    message_text += "📢 Уведомление о бронировании\n\n"
    message_text += "Подробности уточняйте у менеджеров!"

    # Отправляем сообщение с возвратом ссылки
    success, message_link = await sender.send_message_async(
        channel_identifier=chat['chat_name'],
        message=message_text,
        return_message_link=True
    )

    if success and message_link:
      # Сохраняем результат отправки
      message_id = message_link.split('/')[-1] if message_link else ''
      save_send_result(chat['chat_name'], message_id, message_link)

      current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
      result_message = (
        f"✅ **Успешно отправлено**\n"
        f"📢 Канал: {chat['channel_name'] or chat['chat_name']}\n"
        f"🆔 ID сообщения: {message_id}\n"
        f"📅 Время отправки: {current_time}\n"
        f"🔗 Ссылка: {message_link}"
      )

      # Отправляем результат через tg_notifier
      await send_result_to_bot(update, result_message)

      return True, message_link
    else:
      error_message = (
        f"❌ **Ошибка отправки**\n"
        f"📢 Канал: {chat['channel_name'] or chat['chat_name']}\n"
        f"⚠️ Не удалось отправить сообщение"
      )
      await send_result_to_bot(update, error_message)
      return False, None

  except Exception as e:
    logger.error(f"Error sending to {chat['chat_name']}: {e}")
    error_message = (
      f"❌ **Ошибка отправки**\n"
      f"📢 Канал: {chat['channel_name'] or chat['chat_name']}\n"
      f"💥 Ошибка: {str(e)}"
    )
    await send_result_to_bot(update, error_message)
    return False, None


async def send_result_to_bot(update, message):
  """Отправка результата боту через tg_notifier"""
  try:
    # Получаем chat_id пользователя
    if update.callback_query:
      chat_id = update.callback_query.message.chat_id
    elif update.message:
      chat_id = update.message.chat_id
    else:
      return False

    # Создаем сессию для отправки
    async with aiohttp.ClientSession() as session:
      return await send_telegram_message(
          session=session,
          chat_id=chat_id,
          message=message,
          timeout_sec=10,
          parse_mode='Markdown'
      )

  except Exception as e:
    logger.error(f"Error sending result to bot: {e}")
    return False


async def start_broadcast(update, context, object_name):
  """Запуск массовой рассылки по всем доступным каналам"""
  logger.info(f"Starting broadcast for object: {object_name}")

  try:
    # Получаем доступные чаты
    if object_name == 'all':
      available_chats = await get_available_chats_for_object('all')
      object_display_name = "Все объекты"
    else:
      available_chats = await get_available_chats_for_object(object_name)
      objects_data = get_all_booking_files()
      object_display_name = objects_data.get(object_name, {}).get(
          'display_name', object_name)

    if not available_chats:
      await send_reply(update, "❌ Нет доступных каналов для рассылки")
      return

    # Отправляем сообщение о начале рассылки
    await send_reply(
        update,
        f"🚀 **Начинаем рассылку**\n"
        f"🏢 Объект: {object_display_name}\n"
        f"📊 Каналов для отправки: {len(available_chats)}\n"
        f"⏳ Ожидайте результаты в реальном времени...",
        parse_mode='Markdown'
    )

    # Создаем отправитель (для обратной совместимости)
    from telega.send_tg_reklama import TelegramSender
    sender = TelegramSender()

    success_count = 0
    failed_count = 0

    # Создаем задачи для асинхронной отправки
    tasks = []
    for chat in available_chats:
      task = send_broadcast_to_chat(sender, chat, object_display_name, update)
      tasks.append(task)

    # Запускаем все задачи параллельно с ограничением одновременных запросов
    semaphore = asyncio.Semaphore(3)  # Максимум 3 одновременные отправки

    async def bounded_task(task):
      async with semaphore:
        return await task

    bounded_tasks = [bounded_task(task) for task in tasks]
    results = await asyncio.gather(*bounded_tasks, return_exceptions=True)

    # Обрабатываем результаты
    for result in results:
      if isinstance(result, Exception):
        failed_count += 1
        logger.error(f"Exception in broadcast task: {result}")
      else:
        success, _ = result
        if success:
          success_count += 1
        else:
          failed_count += 1

    # Отправляем финальное сообщение о завершении
    completion_message = (
      f"🎉 **Рассылка завершена!**\n\n"
      f"🏢 Объект: {object_display_name}\n"
      f"✅ Успешно: {success_count}\n"
      f"❌ Ошибок: {failed_count}\n"
      f"📊 Всего: {len(available_chats)}\n\n"
      f"Для новой рассылки начните заново."
    )

    await send_result_to_bot(update, completion_message)

  except Exception as e:
    logger.error(f"Error in start_broadcast: {e}", exc_info=True)
    error_message = f"❌ **Критическая ошибка при рассылке:** {str(e)}"
    await send_result_to_bot(update, error_message)


async def send_reply(update, text, reply_markup=None, parse_mode=None):
  """Универсальная функция отправки сообщения"""
  logger.debug(f"Preparing to send reply with text: {text}")
  try:
    if update.callback_query:
      logger.debug("Sending reply to callback_query")
      return await update.callback_query.message.reply_text(
          text,
          reply_markup=reply_markup,
          parse_mode=parse_mode
      )
    elif update.message:
      logger.debug("Sending reply to message")
      return await update.message.reply_text(
          text,
          reply_markup=reply_markup,
          parse_mode=parse_mode
      )
    logger.debug("Reply sent successfully")
  except Exception as e:
    logger.error(f"Error in send_reply: {e}", exc_info=True)
    raise