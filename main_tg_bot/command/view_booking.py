# main_tg_bot/command/view_booking.py (или как у вас)
import os
from datetime import date
from pathlib import Path

import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT, get_all_booking_files

logger = setup_logger("view_booking")

# Определяем путь к папке booking относительно корня проекта
BOOKING_DATA_DIR = PROJECT_ROOT / Config.BOOKING_DATA_DIR

# Префиксы для callback
VB_CALLBACK_PREFIX = "vb_"
VB_SHEET_SELECT = f"{VB_CALLBACK_PREFIX}sheet"



def format_file_name(file_name: str) -> str:
    """Форматирование имени файла для отображения в Telegram"""
    name = file_name.replace('.csv', '').replace('_', ' ').title()
    return name


async def view_booking_handler(update, context):
    try:
        logger.info(f"view_booking_handler called with update type: {type(update)}")

        if update.callback_query:
            if update.callback_query.data.startswith(VB_CALLBACK_PREFIX):
                return await handle_callback(update, context)
            else:
                logger.info(f"Callback not for view_booking, skipping: {update.callback_query.data}")
                return
        elif update.message:
            return await handle_message(update, context)
        else:
            logger.error("Unknown update type in view_booking_handler")

    except Exception as e:
        logger.error(f"Error in view_booking_handler: {e}", exc_info=True)
        error_message = "Произошла ошибка при обработке запроса"
        await send_reply(update, error_message)


async def handle_message(update, context):
    try:
        step = context.user_data.get('step', 1)
        if step == 1:
            await show_file_selection(update, context)
            context.user_data['step'] = 2
        elif step == 2:
            selected_file = update.message.text.strip()
            # Сразу сбросим шаг, чтобы избежать повторного срабатывания
            context.user_data.pop('step', None)
            await show_bookings(update, context, selected_file)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}", exc_info=True)
        context.user_data.pop('step', None)  # на всякий случай

async def handle_callback(update, context):
    try:
        query = update.callback_query
        await query.answer()

        if query.data.startswith(VB_SHEET_SELECT):
            selected_file = query.data.replace(f"{VB_SHEET_SELECT}_", "")
            await show_bookings(update, context, selected_file)

        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")

        if 'step' in context.user_data:
            del context.user_data['step']

    except Exception as e:
        logger.error(f"Error in handle_callback: {e}", exc_info=True)


async def show_file_selection(update, context):
    try:
        csv_files = get_all_booking_files()
        if not csv_files:
            await send_reply(update, "📭 Нет доступных файлов бронирований в папке `booking/`")
            return

        logger.info(f"Available CSV files: {csv_files}")

        keyboard = []
        for file_name in csv_files:
            display_name = format_file_name(file_name)
            callback_data = f"{VB_SHEET_SELECT}_{file_name}"
            keyboard.append([InlineKeyboardButton(display_name, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_reply(update, "Выберите файл для просмотра бронирований:", reply_markup)

    except Exception as e:
        logger.error(f"Error in show_file_selection: {e}", exc_info=True)
        await send_reply(update, "Ошибка при получении списка файлов")


def get_file_path(file_name: str) -> str:
    return str(BOOKING_DATA_DIR / file_name)


def load_bookings_from_csv(file_name: str):
    try:
        file_path = get_file_path(file_name)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        df = pd.read_csv(file_path, encoding='utf-8')
        df = df.fillna('')

        # Проверяем наличие обязательных колонок
        required_cols = {'Заезд', 'Выезд'}
        if not required_cols.issubset(df.columns):
            logger.error(f"Missing required columns in {file_name}. Found: {df.columns.tolist()}")
            return None

        df['Заезд'] = pd.to_datetime(df['Заезд'], format='%d.%m.%Y', errors='coerce')
        df['Выезд'] = pd.to_datetime(df['Выезд'], format='%d.%m.%Y', errors='coerce')
        df = df.dropna(subset=['Заезд', 'Выезд'])

        return df
    except Exception as e:
        logger.error(f"Error loading CSV file {file_name}: {e}", exc_info=True)
        return None


async def show_bookings(update, context, file_name: str):
  try:
    csv_files = get_all_booking_files()
    if file_name not in csv_files:
      await send_reply(update,
                       f"❌ Файл {file_name} не найден в папке `booking/`")
      return

    df = load_bookings_from_csv(file_name)
    if df is None:
      await send_reply(update,
                       f"❌ Не удалось загрузить данные из файла {file_name}")
      return

    if df.empty:
      await send_reply(update, f"📭 Файл {file_name} не содержит данных")
      return

    today = date.today()
    active_bookings = df[df['Выезд'].dt.date >= today].copy()
    active_bookings = active_bookings.sort_values('Заезд')

    if active_bookings.empty:
      await send_reply(update,
                       f"📭 Нет активных бронирований в файле {format_file_name(file_name)}")
      return

    messages = prepare_booking_messages(file_name, active_bookings)
    for msg in messages:
      await send_reply(update, msg, parse_mode='HTML')

    # Информация о типе файла
    if "booking_other" in file_name.lower():
      await send_reply(update,
                       "ℹ️ Для этого файла не показываются свободные периоды между бронированиями.")

  except Exception as e:
    logger.error(f"Error in show_bookings: {e}", exc_info=True)
    await send_reply(update, "❌ Ошибка при получении данных о бронированиях")


def format_date(dt):
    if hasattr(dt, 'strftime'):
        return dt.strftime("%d.%m.%Y")
    return str(dt)


def prepare_booking_messages(file_name: str, bookings_df):
  messages = []
  display_file_name = format_file_name(file_name)
  current_message = f"<b>📅 Бронирования из файла {display_file_name}:</b>\n\n"

  # Флаг для определения, нужно ли показывать свободные периоды
  show_free_periods = "booking_other" not in file_name.lower()

  # Проверяем наличие дополнительных колонок для booking_other
  additional_columns = []
  if "booking_other" in file_name.lower():
    for col in ["Название кондо", "Номер апарта", "Хозяин"]:
      if col in bookings_df.columns:
        additional_columns.append(col)

  bookings = bookings_df.to_dict('records')
  for i, booking in enumerate(bookings):
    guest = booking.get('Гость', 'Не указан')
    check_in = booking.get('Заезд')
    check_out = booking.get('Выезд')

    nights = (check_out - check_in).days if check_in and check_out else 0

    # Формируем основную информацию о брони
    booking_info = (
      f"<b>🏠 Бронь #{i + 1}</b>\n"
    )

    # Добавляем дополнительные поля для booking_other
    if additional_columns:
      extra_info = []
      for col in additional_columns:
        value = booking.get(col, '')
        if value:
          extra_info.append(str(value))

      if extra_info:
        booking_info += f"<b>📍 Хозяин ({', '.join(extra_info)})</b>\n"

    booking_info += (
      f"<b>{guest}</b>\n"
      f"📅 {format_date(check_in)} - {format_date(check_out)}\n"
      f"🌙 Ночей: {nights}\n"
      f"💵 Сумма: {booking.get('СуммаБатты', 'Не указана')} батт\n\n"
    )

    if len(current_message + booking_info) > 4000:
      messages.append(current_message)
      current_message = booking_info
    else:
      current_message += booking_info

    # Свободные периоды (только если нужно показывать)
    if show_free_periods and i < len(bookings) - 1:
      next_check_in = bookings[i + 1].get('Заезд')
      if check_out and next_check_in and check_out != next_check_in:
        free_nights = (next_check_in - check_out).days
        if free_nights > 0:
          free_period = (
            f"🆓 Свободно:\n"
            f"📅 С {format_date(check_out)} - По {format_date(next_check_in)}\n"
            f"🌙 {free_nights} ночей\n\n"
          )
          if len(current_message + free_period) > 4000:
            messages.append(current_message)
            current_message = free_period
          else:
            current_message += free_period

  messages.append(current_message)
  return messages

async def send_reply(update, text, reply_markup=None, parse_mode=None):
    try:
        if update.callback_query:
            return await update.callback_query.message.reply_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        elif update.message:
            return await update.message.reply_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
    except Exception as e:
        logger.error(f"Error in send_reply: {e}", exc_info=True)