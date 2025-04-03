from datetime import datetime, timedelta, time as dt_time
from sqlalchemy import select, and_
from common.database import SessionLocal
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking, Notification
from common.config import Config
from typing import Optional
import aiohttp  # Заменяем requests на асинхронный aiohttp

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
            max_trigger_days = session.execute(
                select(Notification.trigger_days)
            ).scalar()

            if max_trigger_days is None:
                logger.info("Нет уведомлений для обработки")
                return

            trigger_objects = session.execute(
                select(Notification.trigger_object).distinct()
            ).scalars().all()

            if not trigger_objects:
                logger.info("Нет объектов для триггеров")
                return

            date_threshold = current_date - timedelta(days=max_trigger_days)
            bookings = session.execute(
                select(Booking).where(
                    and_(
                        Booking.sheet_name.in_(trigger_objects),
                        Booking.check_out >= date_threshold
                    )
                )
            ).scalars().all()

            if not bookings:
                logger.info("Нет подходящих бронирований для проверки")
                return

            notifications = session.execute(
                select(Notification)
            ).scalars().all()

            # Создаем сессию aiohttp для всех запросов
            async with aiohttp.ClientSession() as http_session:
                for booking in bookings:
                    for notification in notifications:
                        if (booking.sheet_name == notification.trigger_object and
                            is_time_in_window(notification.start_time, current_datetime)):

                            booking_date, date_type = get_booking_date(booking, notification)
                            if booking_date and is_trigger_day(booking_date, current_date, notification.trigger_days):
                                await send_notification(http_session, booking, notification, booking_date, date_type)

    except Exception as e:
        logger.error(f"Ошибка при проверке триггеров: {str(e)}", exc_info=True)

def is_time_in_window(target_time: Optional[dt_time], current_time: datetime, window_minutes: int = 30) -> bool:
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
    """Проверяет совпадение дней до события"""
    return abs((booking_date - current_date).days) == abs(trigger_days)


async def send_notification(http_session, booking: Booking,
    notification: Notification, booking_date, date_type: str):
  """Формирует и отправляет уведомление"""
  trigger_info = format_notification_message(booking, notification,
                                             booking_date, date_type)
  await send_telegram_message(http_session, trigger_info)
  await send_telegram_message(http_session, notification.message)
  logger.info(f"Отправлено уведомление для бронирования ID: {booking.id}")


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
    return (
        "🔔 <b>Сработало уведомление</b> 🔔\n"
        f"🏠 <b>Объект:</b> {notification.trigger_object}\n"
        f"👤 <b>Гость:</b> {booking.guest or 'Не указан'}\n"
        f"📅 <b>Даты:</b> {booking.check_in.strftime('%d.%m.%Y') if booking.check_in else 'Не указана'} - "
        f"{booking.check_out.strftime('%d.%m.%Y') if booking.check_out else 'Не указана'}\n"
        f"⏰ <b>Тип уведомления:</b> {notification.notification_type}\n"
        f"📆 <b>Триггер дата {date_type}:</b> {booking_date.strftime('%d.%m.%Y')}\n"
        f"📌 <b>Триггер по:</b> {date_type}\n"
        f"⏳ <b>Дней до {date_type}:</b> {notification.trigger_days}\n"
        f"🕒 <b>Время уведомления:</b> {notification.start_time.strftime('%H:%M') if notification.start_time else 'Любое'}\n"
        f"📋 <b>ID брони:</b> {booking.id}\n\n"
        "<b>Сообщение:</b>"
    )
