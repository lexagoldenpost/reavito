from datetime import date
from sqlalchemy import select, and_
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from common.database import SessionLocal
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking

logger = setup_logger("view_booking")

# Добавляем префиксы для callback-данных
VB_CALLBACK_PREFIX = "vb_"  # vb = view_booking
VB_SHEET_SELECT = f"{VB_CALLBACK_PREFIX}sheet"


async def view_booking_handler(update, context):
  """Обработчик для просмотра бронирований"""
  try:
    if update.callback_query:
      # Проверяем, что callback относится к этому модулю
      if update.callback_query.data.startswith(VB_CALLBACK_PREFIX):
        return await handle_callback(update, context)
      else:
        # Пропускаем callback, если он не для этого модуля
        return
    elif update.message:
      return await handle_message(update, context)
    else:
      logger.error("Unknown update type in view_booking_handler")

  except Exception as e:
    logger.error(f"Error in view_booking_handler: {e}")
    error_message = "Произошла ошибка при обработке запроса"
    await send_reply(update, error_message)


async def handle_message(update, context):
  """Обработка текстового сообщения"""
  if 'step' not in context.user_data or context.user_data['step'] == 1:
    await show_sheet_names(update, context)
    context.user_data['step'] = 2
  elif context.user_data['step'] == 2:
    selected_sheet = update.message.text.strip()
    await show_bookings(update, context, selected_sheet)
    del context.user_data['step']


async def handle_callback(update, context):
  """Обработка нажатия на кнопку"""
  query = update.callback_query
  await query.answer()

  if query.data.startswith(VB_SHEET_SELECT):
    selected_sheet = query.data.split('_')[2]
    await show_bookings(update, context, selected_sheet)

  try:
    await query.message.delete()
  except Exception as e:
    logger.warning(f"Could not delete message: {e}")

  if 'step' in context.user_data:
    del context.user_data['step']


async def show_sheet_names(update, context):
  """Показать пользователю список уникальных sheet_name с кнопками"""
  try:
    with SessionLocal() as session:
      stmt = select(Booking.sheet_name).distinct()
      result = session.execute(stmt)
      sheet_names = [row[0] for row in result if row[0]]

      if not sheet_names:
        await send_reply(update, "Нет доступных вариантов для выбора")
        return

      keyboard = [
        [InlineKeyboardButton(sheet,
                              callback_data=f"{VB_SHEET_SELECT}_{sheet}")]
        for sheet in sheet_names
      ]
      reply_markup = InlineKeyboardMarkup(keyboard)

      await send_reply(update, "Выберите вариант:", reply_markup)

  except Exception as e:
    logger.error(f"Error in show_sheet_names: {e}")
    await send_reply(update, "Ошибка при получении данных")


async def show_bookings(update, context, sheet_name):
  """Показать бронирования для выбранного sheet_name"""
  try:
    with SessionLocal() as session:
      today = date.today()
      stmt = select(Booking).where(
          and_(
              Booking.sheet_name == sheet_name,
              Booking.check_out >= today
          )
      ).order_by(Booking.check_in)

      result = session.execute(stmt)
      bookings = result.scalars().all()

      if not bookings:
        await send_reply(update, f"Нет активных бронирований для {sheet_name}")
        return

      messages = prepare_booking_messages(sheet_name, bookings)

      for msg in messages:
        await send_reply(update, msg, parse_mode='HTML')

  except Exception as e:
    logger.error(f"Error in show_bookings: {e}")
    await send_reply(update, "Ошибка при получении данных о бронированиях")


def format_date(dt):
  """Форматирование даты в dd.mm.yyyy"""
  return dt.strftime("%d.%m.%Y")


def prepare_booking_messages(sheet_name, bookings):
  """Подготовка сообщений с информацией о бронированиях"""
  messages = []
  current_message = f"<b>📅 Бронирования для {sheet_name}:</b>\n\n"

  for i in range(len(bookings)):
    booking = bookings[i]
    booking_info = (
      f"<b>🏠 Бронь #{i + 1}</b>\n"
      f"<b>{booking.guest}</b>\n"
      f"📅 {format_date(booking.check_in)} - {format_date(booking.check_out)}\n"
      f"🌙 Ночей: {(booking.check_out - booking.check_in).days}\n\n"
    )

    if len(current_message + booking_info) > 4000:
      messages.append(current_message)
      current_message = booking_info
    else:
      current_message += booking_info

    if i < len(bookings) - 1:
      next_booking = bookings[i + 1]
      if booking.check_out != next_booking.check_in:
        nights = (next_booking.check_in - booking.check_out).days
        free_period = (
          f"🆓 Свободно:\n"
          f"📅 С {format_date(booking.check_out)} - По {format_date(next_booking.check_in)}\n"
          f"🌙 {nights} ночей\n\n"
        )

        if len(current_message + free_period) > 4000:
          messages.append(current_message)
          current_message = free_period
        else:
          current_message += free_period

  messages.append(current_message)
  return messages


async def send_reply(update, text, reply_markup=None, parse_mode=None):
  """Универсальная функция отправки сообщения"""
  if update.callback_query:
    await update.callback_query.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
  elif update.message:
    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )