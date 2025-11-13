from datetime import date, datetime

from common.database import SessionLocal
from sqlalchemy import select, and_
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

from common.logging_config import setup_logger
from old.sync_db_google_sheets.models import Booking
from sync_google_booking import update_single_record_in_google_sheet

logger = setup_logger("edit_booking")

# Состояния для ConversationHandler
SELECT_SHEET, SELECT_BOOKING, EDIT_FIELD, EDIT_VALUE = range(4)


def format_booking_data(booking):
  """Форматирование данных бронирования в читаемый вид"""
  nights = (
        booking.check_out - booking.check_in).days if booking.check_in and booking.check_out else 0

  data = {
    'sheet_name': booking.sheet_name,
    'guest': booking.guest,
    'booking_date': booking.booking_date.strftime(
      '%d-%m-%Y') if booking.booking_date else 'N/A',
    'check_in': booking.check_in.strftime(
      '%d-%m-%Y') if booking.check_in else 'N/A',
    'check_out': booking.check_out.strftime(
      '%d-%m-%Y') if booking.check_out else 'N/A',
    'nights': nights,
    'monthly_sum': getattr(booking, 'monthly_sum', 'N/A'),
    'total_sum': getattr(booking, 'total_sum', 'N/A'),
    'advance': getattr(booking, 'advance', 'N/A'),
    'additional_payment': getattr(booking, 'additional_payment', 'N/A'),
    'source': getattr(booking, 'source', 'N/A'),
    'extra_charges': getattr(booking, 'extra_charges', 'N/A'),
    'expenses': getattr(booking, 'expenses', 'N/A'),
    'payment_method': getattr(booking, 'payment_method', 'N/A'),
    'comments': getattr(booking, 'comments', 'N/A'),
    'phone': booking.phone,
    'additional_phone': getattr(booking, 'additional_phone', 'N/A'),
    'flights': getattr(booking, 'flights', 'N/A')
  }

  message = (
    f"Таблица: {data['sheet_name']}\n"
    f"Гость: {data['guest']}\n"
    f"Дата бронирования: {data['booking_date']}\n"
    f"Дата заезда: {data['check_in']}\n"
    f"Дата выезда: {data['check_out']}\n"
    f"Количество ночей: {data['nights']}\n"
    f"Сумма по месяцам: {data['monthly_sum']}\n"
    f"Общая сумма: {data['total_sum']}\n"
    f"Аванс: {data['advance']}\n"
    f"Доплата: {data['additional_payment']}\n"
    f"Источник бронирования: {data['source']}\n"
    f"Доп. платежи: {data['extra_charges']}\n"
    f"Расходы: {data['expenses']}\n"
    f"Способ оплаты: {data['payment_method']}\n"
    f"Комментарий: {data['comments']}\n"
    f"Телефон: {data['phone']}\n"
    f"Доп. телефон: {data['additional_phone']}\n"
    f"Информация о рейсах: {data['flights']}"
  )

  return message, data


async def edit_booking_start(update: Update, context: CallbackContext) -> int:
  """Начало процесса редактирования - выбор sheet_name"""
  with SessionLocal() as session:
    sheets = session.execute(
        select(Booking.sheet_name).distinct()
    ).scalars().all()

    if not sheets:
      await update.message.reply_text(
        "Нет доступных бронирований для редактирования.")
      return ConversationHandler.END

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
  query = update.callback_query
  await query.answer()

  if query.data == "back_to_sheets":
    return await edit_booking_start(update, context)

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
      return ConversationHandler.END

    keyboard = [
      [InlineKeyboardButton(
          f"{b.guest} ({b.check_in} - {b.check_out})",
          callback_data=f"booking_{b.id}"
      )]
      for b in bookings
    ]
    keyboard.append(
        [InlineKeyboardButton("Назад", callback_data="back_to_sheets")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Выберите бронирование для {sheet_name}:",
        reply_markup=reply_markup
    )

  return SELECT_BOOKING


async def select_booking(update: Update, context: CallbackContext) -> int:
  """Обработка выбора конкретного бронирования"""
  query = update.callback_query
  await query.answer()

  if query.data == "back_to_sheets":
    return await select_sheet(update, context)

  booking_id = int(query.data.replace("booking_", ""))
  context.user_data['edit_booking']['booking_id'] = booking_id

  with SessionLocal() as session:
    booking = session.get(Booking, booking_id)

    if not booking:
      await query.edit_message_text("Бронирование не найдено!")
      return ConversationHandler.END

    message, booking_data = format_booking_data(booking)
    context.user_data['edit_booking']['data'] = booking_data
    context.user_data['edit_booking']['original'] = booking

    # Создаем клавиатуру для выбора поля
    fields = [
      ("guest", "Гость"),
      ("booking_date", "Дата бронирования"),
      ("check_in", "Дата заезда"),
      ("check_out", "Дата выезда"),
      ("phone", "Телефон"),
      ("additional_phone", "Доп. телефон"),
      ("source", "Источник бронирования"),
      ("payment_method", "Способ оплаты"),
      ("comments", "Комментарий"),
      ("flights", "Информация о рейсах")
    ]

    keyboard = []
    for field_key, field_name in fields:
      if field_key in booking_data:
        keyboard.append([InlineKeyboardButton(
            f"✏️ {field_name}: {booking_data[field_key]}",
            callback_data=f"edit_{field_key}"
        )])

    keyboard.append([InlineKeyboardButton("✅ Сохранить изменения",
                                          callback_data="save_booking")])
    keyboard.append(
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel_edit")])
    keyboard.append([InlineKeyboardButton("↩️ Назад к списку",
                                          callback_data="back_to_bookings")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"📝 Редактирование бронирования:\n\n{message}\n\nВыберите поле для редактирования:",
        reply_markup=reply_markup
    )

  return EDIT_FIELD


async def select_field_to_edit(update: Update, context: CallbackContext) -> int:
  """Выбор поля для редактирования"""
  query = update.callback_query
  await query.answer()

  if query.data == "back_to_bookings":
    return await select_sheet(update, context)
  if query.data == "cancel_edit":
    return await cancel_edit(update, context)
  if query.data == "save_booking":
    return await save_booking(update, context)

  field_key = query.data.replace("edit_", "")
  context.user_data['edit_booking']['current_field'] = field_key

  field_names = {
    "guest": "Гость",
    "booking_date": "Дата бронирования (ДД-ММ-ГГГГ)",
    "check_in": "Дата заезда (ДД-ММ-ГГГГ)",
    "check_out": "Дата выезда (ДД-ММ-ГГГГ)",
    "phone": "Телефон",
    "additional_phone": "Доп. телефон",
    "source": "Источник бронирования",
    "payment_method": "Способ оплаты",
    "comments": "Комментарий",
    "flights": "Информация о рейсах"
  }

  await query.edit_message_text(
      f"Введите новое значение для поля '{field_names[field_key]}':\n"
      f"Текущее значение: {context.user_data['edit_booking']['data'][field_key]}"
  )

  return EDIT_VALUE


async def edit_field_value(update: Update, context: CallbackContext) -> int:
  """Обработка нового значения поля"""
  new_value = update.message.text
  field_key = context.user_data['edit_booking']['current_field']

  # Валидация дат
  date_fields = ["booking_date", "check_in", "check_out"]
  if field_key in date_fields:
    try:
      parsed_date = datetime.strptime(new_value, "%d-%m-%Y").date()
      context.user_data['edit_booking']['data'][
        field_key] = parsed_date.strftime('%d-%m-%Y')
    except ValueError:
      await update.message.reply_text(
        "Неверный формат даты. Используйте ДД-ММ-ГГГГ")
      return EDIT_VALUE
  else:
    context.user_data['edit_booking']['data'][field_key] = new_value

  # Возвращаемся к просмотру всех полей
  return await show_booking_for_edit(update, context)


async def show_booking_for_edit(update: Update,
    context: CallbackContext) -> int:
  """Показ бронирования после редактирования"""
  booking_data = context.user_data['edit_booking']['data']

  # Создаем временный объект Booking для форматирования
  temp_booking = Booking(
      sheet_name=booking_data['sheet_name'],
      guest=booking_data['guest'],
      phone=booking_data['phone'],
      check_in=datetime.strptime(booking_data['check_in'], "%d-%m-%Y").date() if
      booking_data['check_in'] != 'N/A' else None,
      check_out=datetime.strptime(booking_data['check_out'],
                                  "%d-%m-%Y").date() if booking_data[
                                                          'check_out'] != 'N/A' else None,
      booking_date=datetime.strptime(booking_data['booking_date'],
                                     "%d-%m-%Y").date() if booking_data[
                                                             'booking_date'] != 'N/A' else None,
      comments=booking_data['comments'],
      additional_phone=booking_data['additional_phone']
  )

  # Устанавливаем дополнительные атрибуты
  for field in ['source', 'payment_method', 'flights', 'monthly_sum',
                'total_sum', 'advance', 'additional_payment',
                'extra_charges', 'expenses']:
    if field in booking_data and booking_data[field] != 'N/A':
      setattr(temp_booking, field, booking_data[field])

  message, _ = format_booking_data(temp_booking)

  fields = [
    ("guest", "Гость"),
    ("booking_date", "Дата бронирования"),
    ("check_in", "Дата заезда"),
    ("check_out", "Дата выезда"),
    ("phone", "Телефон"),
    ("additional_phone", "Доп. телефон"),
    ("source", "Источник бронирования"),
    ("payment_method", "Способ оплаты"),
    ("comments", "Комментарий"),
    ("flights", "Информация о рейсах")
  ]

  keyboard = []
  for field_key, field_name in fields:
    if field_key in booking_data:
      keyboard.append([InlineKeyboardButton(
          f"✏️ {field_name}: {booking_data[field_key]}",
          callback_data=f"edit_{field_key}"
      )])

  keyboard.append([InlineKeyboardButton("✅ Сохранить изменения",
                                        callback_data="save_booking")])
  keyboard.append(
      [InlineKeyboardButton("❌ Отменить", callback_data="cancel_edit")])
  keyboard.append([InlineKeyboardButton("↩️ Назад к списку",
                                        callback_data="back_to_bookings")])

  reply_markup = InlineKeyboardMarkup(keyboard)

  if hasattr(update, 'message'):
    await update.message.reply_text(
        f"📝 Редактирование бронирования:\n\n{message}\n\nВыберите поле для редактирования:",
        reply_markup=reply_markup
    )
  else:
    await update.callback_query.edit_message_text(
        f"📝 Редактирование бронирования:\n\n{message}\n\nВыберите поле для редактирования:",
        reply_markup=reply_markup
    )

  return EDIT_FIELD


async def save_booking(update: Update, context: CallbackContext) -> int:
  """Сохранение изменений в БД"""
  query = update.callback_query
  await query.answer()

  user_data = context.user_data['edit_booking']
  booking_data = user_data['data']

  with SessionLocal() as session:
    booking = session.get(Booking, user_data['booking_id'])
    if not booking:
      await query.edit_message_text("❌ Ошибка: бронирование не найдено в БД")
      return ConversationHandler.END

    # Обновляем основные поля
    booking.sheet_name = booking_data['sheet_name']
    booking.guest = booking_data['guest']
    booking.phone = booking_data['phone']
    booking.comments = booking_data['comments']
    booking.additional_phone = booking_data['additional_phone']

    # Обновляем даты
    if booking_data['check_in'] != 'N/A':
      booking.check_in = datetime.strptime(booking_data['check_in'],
                                           "%d-%m-%Y").date()
    if booking_data['check_out'] != 'N/A':
      booking.check_out = datetime.strptime(booking_data['check_out'],
                                            "%d-%m-%Y").date()
    if booking_data['booking_date'] != 'N/A':
      booking.booking_date = datetime.strptime(booking_data['booking_date'],
                                               "%d-%m-%Y").date()

    # Обновляем дополнительные поля
    for field in ['source', 'payment_method', 'flights', 'monthly_sum',
                  'total_sum', 'advance', 'additional_payment',
                  'extra_charges', 'expenses']:
      if field in booking_data and booking_data[field] != 'N/A':
        setattr(booking, field, booking_data[field])

    session.commit()
    await query.edit_message_text("✅ Бронирование успешно обновлено!")

    result = update_single_record_in_google_sheet(
        record_id=booking.id,
        # Используем id из объекта booking, а не из booking_data
        sheet_name=booking.sheet_name
    )

    if result["status"] == "success":
      await query.edit_message_text(
        "✅ Бронирование успешно обновлено в гугл таблице!")
    else:
      await query.edit_message_text(
        f"❌ Ошибка обновления в гугл таблице! - {result['message']}")
  return ConversationHandler.END


async def cancel_edit(update: Update, context: CallbackContext) -> int:
  """Отмена редактирования"""
  query = update.callback_query
  await query.answer()

  await query.edit_message_text(
    "❌ Изменения отменены. Бронирование не было изменено.")
  return ConversationHandler.END


# ConversationHandler должен быть определен после всех функций
edit_booking_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('edit_booking', edit_booking_start)],
    states={
      SELECT_SHEET: [CallbackQueryHandler(select_sheet, pattern="^sheet_")],
      SELECT_BOOKING: [
        CallbackQueryHandler(select_booking, pattern="^booking_"),
        CallbackQueryHandler(cancel_edit, pattern="^back_to_sheets")
      ],
      EDIT_FIELD: [
        CallbackQueryHandler(select_field_to_edit, pattern="^edit_"),
        CallbackQueryHandler(save_booking, pattern="^save_booking"),
        CallbackQueryHandler(cancel_edit, pattern="^cancel_edit"),
        CallbackQueryHandler(select_sheet, pattern="^back_to_bookings")
      ],
      EDIT_VALUE: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_value)
      ]
    },
    fallbacks=[CommandHandler('cancel', cancel_edit)],
    allow_reentry=True
)