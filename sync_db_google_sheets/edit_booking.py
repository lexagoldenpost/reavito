from datetime import date, datetime
from sqlalchemy import select, and_
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
  CommandHandler,
  CallbackContext,
  CallbackQueryHandler,
  MessageHandler,
  filters,
  ConversationHandler,
  ContextTypes,
)
from common.database import SessionLocal
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking

logger = setup_logger("edit_booking")

# Состояния для ConversationHandler
SELECT_SHEET, SELECT_BOOKING, EDIT_BOOKING = range(3)


async def edit_booking_start(update: Update, context: CallbackContext) -> int:
  """Начало процесса редактирования - выбор sheet_name"""
  with SessionLocal() as session:
    sheets = session.execute(
        select(Booking.sheet_name).distinct()
    ).scalars().all()

    if not sheets:
      await update.message.reply_text(
          "Нет доступных бронирований для редактирования.")
      return -1

    keyboard = [
      [InlineKeyboardButton(sheet, callback_data=f"sheet_{sheet}")]
      for sheet in sheets
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выберите объект для редактирования:",
        reply_markup=reply_markup
    )

  return SELECT_SHEET


async def select_sheet(update: Update, context: CallbackContext) -> int:
  """Обработка выбора sheet_name и показ бронирований"""
  query = update
  if hasattr(update, 'callback_query'):
    query = update.callback_query
    await query.answer()

  sheet_name = query.data.replace("sheet_", "")
  context.user_data['edit_booking'] = {'sheet_name': sheet_name}

  with SessionLocal() as session:
    bookings = session.execute(
        select(Booking)
        .where(and_(
            Booking.sheet_name == sheet_name,
            Booking.check_out >= date.today()
        ))
        .order_by(Booking.check_in)
    ).scalars().all()

    if not bookings:
      await query.edit_message_text(
          "Нет активных бронирований для этого объекта.")
      return -1

    message_lines = []
    for idx, booking in enumerate(bookings, 1):
      nights = (booking.check_out - booking.check_in).days
      message_lines.append(
          f"{idx}. {booking.guest} - {booking.check_in} - {booking.check_out} ({nights} ночей)"
      )

    message = f"Бронирования для {sheet_name}:\n\n" + "\n".join(message_lines)
    message += "\n\n────────────────────"

    keyboard = [
      [InlineKeyboardButton(
          f"{idx}. {b.guest}",
          callback_data=f"booking_{b.id}"
      )]
      for idx, b in enumerate(bookings, 1)
    ]
    keyboard.append(
        [InlineKeyboardButton("Назад", callback_data="back_to_sheets")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        reply_markup=reply_markup
    )

  return SELECT_BOOKING


async def select_booking(update: Update, context: CallbackContext) -> int:
  """Обработка выбора конкретного бронирования"""
  query = update.callback_query
  await query.answer()

  if query.data == "back_to_sheets":
    return await edit_booking_start(query, context)

  booking_id = int(query.data.replace("booking_", ""))
  context.user_data['edit_booking']['booking_id'] = booking_id

  with SessionLocal() as session:
    booking = session.get(Booking, booking_id)

    if not booking:
      await query.edit_message_text("Бронирование не найдено!")
      return -1

    # Сохраняем только существующие атрибуты
    original_data = {
      'guest': booking.guest,
      'check_in': booking.check_in,
      'check_out': booking.check_out,
      'phone': booking.phone,
      'comments': booking.comments,
    }

    # Добавляем дополнительные атрибуты, если они существуют
    if hasattr(booking, 'booking_date'):
      original_data['booking_date'] = booking.booking_date
    if hasattr(booking, 'additional_phone'):
      original_data['additional_phone'] = booking.additional_phone

    context.user_data['edit_booking']['original'] = original_data

    # Формируем сообщение с текущими данными для редактирования
    message = "📝 Редактирование бронирования:\n\n"
    fields = [
      ("Гость", original_data.get('guest', 'N/A')),
      ("Дата заезда", original_data.get('check_in', 'N/A')),
      ("Дата выезда", original_data.get('check_out', 'N/A')),
      ("Телефон", original_data.get('phone', 'N/A')),
      ("Комментарии", original_data.get('comments', 'N/A'))
    ]

    if 'booking_date' in original_data:
      fields.insert(1, ("Дата бронирования", original_data['booking_date']))
    if 'additional_phone' in original_data:
      fields.append(("Доп. телефон", original_data['additional_phone']))

    for field_name, value in fields:
      message += f"<b>{field_name}:</b> {value}\n"

    message += "\nОтправьте новые данные в формате:\n"
    message += "<code>Гость;Дата заезда (ДД-ММ-ГГГГ);Дата выезда (ДД-ММ-ГГГГ);Телефон;Комментарии"

    if 'booking_date' in original_data:
      message += ";Дата бронирования (ДД-ММ-ГГГГ)"
    if 'additional_phone' in original_data:
      message += ";Доп. телефон"

    message += "</code>"

    keyboard = [
      [InlineKeyboardButton("Отменить", callback_data="cancel_booking")],
      [InlineKeyboardButton("Назад к списку", callback_data="back_to_bookings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

  return EDIT_BOOKING


async def edit_booking_data(update: Update, context: CallbackContext) -> int:
  """Обработка новых данных"""
  user_data = context.user_data['edit_booking']
  original = user_data['original']

  try:
    parts = update.message.text.split(';')
    required_fields = 5  # Основные поля
    if 'booking_date' in original:
      required_fields += 1
    if 'additional_phone' in original:
      required_fields += 1

    if len(parts) != required_fields:
      raise ValueError(
          f"Неверный формат данных. Ожидается {required_fields} полей.")

    # Базовые поля
    guest = parts[0].strip()
    check_in = datetime.strptime(parts[1].strip(), "%d-%m-%Y").date()
    check_out = datetime.strptime(parts[2].strip(), "%d-%m-%Y").date()
    phone = parts[3].strip()
    comments = parts[4].strip()

    if check_in >= check_out:
      await update.message.reply_text(
          "Дата выезда должна быть позже даты заезда!")
      return EDIT_BOOKING

    new_data = {
      'guest': guest,
      'check_in': check_in,
      'check_out': check_out,
      'phone': phone,
      'comments': comments
    }

    # Дополнительные поля
    part_index = 5
    if 'booking_date' in original:
      new_data['booking_date'] = datetime.strptime(parts[part_index].strip(),
                                                   "%d-%m-%Y").date()
      part_index += 1
    if 'additional_phone' in original:
      new_data['additional_phone'] = parts[part_index].strip()

    user_data['new_data'] = new_data

    # Формируем сообщение для подтверждения
    message = "🔍 Подтвердите изменения:\n\n"
    for key, new_value in new_data.items():
      old_value = original.get(key, '')
      message += f"<b>{key.replace('_', ' ').title()}:</b> {new_value} (было: {old_value})\n"

    keyboard = [
      [InlineKeyboardButton("Сохранить", callback_data="save_booking"),
       InlineKeyboardButton("Отменить", callback_data="cancel_booking")],
      [InlineKeyboardButton("Назад к списку", callback_data="back_to_bookings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

  except Exception as e:
    logger.error(f"Ошибка при обработке данных: {e}")
    error_msg = "❌ Ошибка в формате данных. Попробуйте еще раз.\nФормат: "
    error_msg += "Гость;Дата заезда (ДД-ММ-ГГГГ);Дата выезда (ДД-ММ-ГГГГ);Телефон;Комментарии"
    if 'booking_date' in original:
      error_msg += ";Дата бронирования (ДД-ММ-ГГГГ)"
    if 'additional_phone' in original:
      error_msg += ";Доп. телефон"

    await update.message.reply_text(error_msg)
    return EDIT_BOOKING

  return EDIT_BOOKING


async def save_booking(update: Update, context: CallbackContext) -> int:
  """Сохранение изменений в БД"""
  query = update.callback_query
  await query.answer()

  user_data = context.user_data['edit_booking']

  with SessionLocal() as session:
    booking = session.get(Booking, user_data['booking_id'])

    if booking:
      new_data = user_data['new_data']
      for key, value in new_data.items():
        setattr(booking, key, value)

      session.commit()
      await query.edit_message_text("✅ Бронирование успешно обновлено!",
                                    parse_mode="HTML")
    else:
      await query.edit_message_text("❌ Ошибка: бронирование не найдено в БД")

  return -1


async def cancel_edit(update: Update, context: CallbackContext) -> int:
  """Отмена изменений"""
  query = update.callback_query
  await query.answer()

  if query.data == "back_to_bookings":
    return await select_sheet(query, context)

  await query.edit_message_text(
      "❌ Изменения отменены. Бронирование не было изменено.")
  return -1


edit_booking_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('edit_booking', edit_booking_start)],
    states={
        SELECT_SHEET: [CallbackQueryHandler(select_sheet, pattern="^sheet_")],
        SELECT_BOOKING: [
            CallbackQueryHandler(select_booking, pattern="^booking_"),
            CallbackQueryHandler(cancel_edit, pattern="^back_to_sheets")
        ],
        EDIT_BOOKING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_booking_data),
            CallbackQueryHandler(save_booking, pattern="^save_booking"),
            CallbackQueryHandler(cancel_edit, pattern="^cancel_booking"),
            CallbackQueryHandler(cancel_edit, pattern="^back_to_bookings")
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel_edit)],
    allow_reentry=True
)