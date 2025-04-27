from datetime import datetime, timedelta, time as dt_time
from typing import Optional

import aiohttp  # Заменяем requests на асинхронный aiohttp
from sqlalchemy import select, and_

from common.config import Config
from common.database import SessionLocal
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking, Notification

logger = setup_logger("notification_service")

# Конфигурация из переменных окружения
TELEGRAM_BOT_TOKEN = Config.TELEGRAM_BOOKING_BOT_TOKEN
TELEGRAM_CHAT_IDS = Config.TELEGRAM_CHAT_NOTIFICATION_ID


async def check_notification_triggers():
  """Асинхронная проверка триггеров уведомлений"""
  logger.info("Запуск проверки триггеров уведомлений")
  current_datetime = datetime.now()
  current_date = current_datetime.date()

  try:
    with SessionLocal() as session:
      # Получаем все активные уведомления
      notifications = session.execute(
          select(Notification)
      ).scalars().all()

      if not notifications:
        logger.info("Нет уведомлений для обработки")
        return

      # Получаем уникальные объекты для триггеров
      trigger_objects = list({n.trigger_object for n in notifications})

      # Находим максимальный и минимальный trigger_days для оптимизации запроса
      max_trigger_days = max(n.trigger_days for n in notifications)
      min_trigger_days = min(n.trigger_days for n in notifications)

      # Вычисляем границы дат для фильтрации
      date_start = current_date + timedelta(days=min_trigger_days)
      date_end = current_date + timedelta(days=max_trigger_days)

      # Получаем бронирования в нужном диапазоне дат
      bookings = session.execute(
          select(Booking).where(
              and_(
                  Booking.sheet_name.in_(trigger_objects),
                  Booking.check_out >= date_start,
                  Booking.check_in <= date_end
              )
          )
      ).scalars().all()

      if not bookings:
        logger.info("Нет подходящих бронирований для проверки")
        return

      # Создаем сессию aiohttp для всех запросов
      async with aiohttp.ClientSession() as http_session:
        for booking in bookings:
          for notification in notifications:
            if booking.sheet_name != notification.trigger_object:
              continue

            if not is_time_in_window(notification.start_time, current_datetime):
              continue

            booking_date, date_type = get_booking_date(booking, notification)
            if not booking_date:
              continue

            if is_trigger_day(booking_date, current_date,
                              notification.trigger_days):
              await send_notification(http_session, booking, notification,
                                      booking_date, date_type)

  except Exception as e:
    logger.error(f"Ошибка при проверке триггеров: {str(e)}", exc_info=True)

def is_time_in_window(target_time: Optional[dt_time], current_time: datetime, window_minutes: int = 29) -> bool:
    """Проверяет совпадение времени с учетом окна"""
    if target_time is None:
        return True
    target_datetime = datetime.combine(current_time.date(), target_time)
    window = timedelta(minutes=window_minutes)
    return target_datetime - window <= current_time <= target_datetime + window

def get_booking_date(booking: Booking, notification: Notification) -> tuple:
    """Возвращает дату и тип даты для проверки триггера"""
    if notification.trigger_column == 'Заезд':
        return booking.check_in, "заезда"
    elif notification.trigger_column == 'Выезд':
        return booking.check_out, "выезда"
    return None, ""


def is_trigger_day(booking_date, current_date, trigger_days) -> bool:
  """Проверяет совпадение дней до/после события в зависимости от знака trigger_days"""
  delta = (booking_date - current_date).days

  if trigger_days > 0:
    # Положительные значения - проверяем после даты (осталось дней)
    return 0 <= delta <= trigger_days
  elif trigger_days < 0:
    # Отрицательные значения - проверяем до даты (дней до события)
    return trigger_days <= delta <= 0
  else:
    # Нулевое значение - проверяем точное совпадение дат
    return delta == 0


async def send_notification(http_session, booking: Booking,
    notification: Notification, booking_date, date_type: str):
  """Формирует и отправляет уведомление"""
  trigger_info = format_notification_message(booking, notification,
                                             booking_date, date_type)
  # Форматируем сообщение, заменяя {field_name} на значения из booking
  formatted_message = format_message_with_booking_data(notification.message,
                                                       booking)
  await send_telegram_message(http_session, trigger_info)
  await send_telegram_message(http_session, formatted_message)
  logger.info(f"Отправлено уведомление для бронирования ID: {booking.id}")


def format_message_with_booking_data(message: str, booking: Booking) -> str:
  """Заменяет {field_name} в сообщении на значения из объекта Booking"""
  if not message:
    return message

  # Получаем все атрибуты объекта Booking
  booking_fields = vars(booking)

  # Ищем все конструкции {field_name} в сообщении
  formatted_message = message
  for field in booking_fields:
    # Проверяем, есть ли поле в сообщении
    placeholder = f"{{{field}}}"
    if placeholder in formatted_message:
      # Получаем значение поля из booking
      field_value = getattr(booking, field, "")
      # Преобразуем даты в читаемый формат
      if isinstance(field_value, datetime):
        field_value = field_value.strftime('%d.%m.%Y')
      elif field_value is None:
        field_value = ""
      # Заменяем плейсхолдер на значение
      formatted_message = formatted_message.replace(placeholder,
                                                    str(field_value))

  return formatted_message

async def send_telegram_message(http_session, message: str):
  """Асинхронно отправляет сообщение в несколько Telegram чатов"""
  if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
    logger.error("Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_IDS")
    return

  for chat_id in TELEGRAM_CHAT_IDS:
    logger.info(f"Попытка отправки в chat_id {chat_id}")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
      'chat_id': chat_id,
      'text': message,
      'parse_mode': 'HTML'
    }

    try:
      async with http_session.post(url, json=payload) as response:
        if response.status == 200:
          logger.info(f"Сообщение отправлено в чат {chat_id}")
        else:
          error = await response.json()
          logger.error(f"Ошибка при отправке в чат {chat_id}: {error}")
    except Exception as e:
      logger.error(f"Ошибка соединения при отправке в чат {chat_id}: {str(e)}")

def format_notification_message(booking: Booking, notification: Notification, booking_date, date_type: str) -> str:
    """Форматирует сообщение уведомления"""
    trigger_type = "до" if notification.trigger_days < 0 else "после"
    return (
        "🔔 <b>Сработало уведомление</b> 🔔\n"
        f"🏠 <b>Объект:</b> {notification.trigger_object}\n"
        f"👤 <b>Гость:</b> {booking.guest or 'Не указан'}\n"
        f"📅 <b>Даты:</b> {booking.check_in.strftime('%d.%m.%Y') if booking.check_in else 'Не указана'} - "
        f"{booking.check_out.strftime('%d.%m.%Y') if booking.check_out else 'Не указана'}\n"
        f"⏰ <b>Тип уведомления:</b> {notification.notification_type}\n"
        f"📆 <b>Триггер дата {date_type}:</b> {booking_date.strftime('%d.%m.%Y')}\n"
        f"📌 <b>Триггер по:</b> {date_type}\n"
        f"⏳ <b>Дней {trigger_type} {date_type}:</b> {notification.trigger_days}\n"
        f"🕒 <b>Время уведомления:</b> {notification.start_time.strftime('%H:%M') if notification.start_time else 'Любое'}\n"
        f"📋 <b>ID брони:</b> {booking.id}\n\n"
        "<b>Сообщение:</b>"
    )


# if __name__ == "__main__":
#     # Тестовый вызов
#     try:
#         check_notification_triggers()
#         logger.info("Manual check_notification_triggers call succeeded")
#     except Exception as e:
#         logger.error(f"Manual check failed: {e}")

