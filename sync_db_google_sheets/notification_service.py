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
  """Асинхронная проверка триггеров уведомлений
  Дата уведомлений до, положительная, дата уведомления после отрицательная,
  т.к. считаем от текущей даты
  """
  logger.info("Запуск проверки триггеров уведомлений")
  current_datetime = datetime.now()
  current_date = current_datetime.date()
  logger.debug(f"Текущая дата/время: {current_datetime}")

  try:
    with SessionLocal() as session:
      # Получаем все активные уведомления
      logger.debug("Получение списка уведомлений из БД")
      notifications = session.execute(
          select(Notification)
      ).scalars().all()

      if not notifications:
        logger.info("Нет уведомлений для обработки")
        return
      logger.debug(f"Найдено {len(notifications)} уведомлений")

      # Получаем уникальные объекты для триггеров
      trigger_objects = list({n.trigger_object for n in notifications})
      logger.debug(f"Уникальные объекты для триггеров: {trigger_objects}")

      # Находим максимальный и минимальный trigger_days для оптимизации запроса
      max_trigger_days = max(n.trigger_days for n in notifications)
      logger.debug(
        f"Диапазон дней триггера: от -{max_trigger_days} до {max_trigger_days}")

      # Вычисляем границы дат для фильтрации по максимальному значению
      date_start = current_date - timedelta(days=max_trigger_days)
      date_end = current_date + timedelta(days=max_trigger_days)
      logger.info(f"Границы дат для фильтрации: с {date_start} по {date_end}")

      # Получаем бронирования в нужном диапазоне дат
      logger.debug("Поиск бронирований в заданном диапазоне дат")
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
      logger.debug(f"Найдено {len(bookings)} подходящих бронирований")

      # Создаем сессию aiohttp для всех запросов
      async with aiohttp.ClientSession() as http_session:
        for booking in bookings:
          logger.debug(f"Обработка бронирования ID: {booking.id}")
          for notification in notifications:
            logger.debug(f"Проверка уведомления ID: {notification.id}")

            if booking.sheet_name != notification.trigger_object:
              logger.debug(
                f"Объект бронирования '{booking.sheet_name}' не совпадает с триггером '{notification.trigger_object}'")
              continue

            logger.debug(f"Проверка временного окна для уведомления для ИД {notification.id}")
            if not is_time_in_window(notification.start_time, current_datetime):
              logger.debug(
                f"Текущее время не входит в окно уведомления (время триггера: {notification.start_time})")
              continue

            is_trigger_day, booking_date, date_type = get_booking_date(booking, notification)
            if not booking_date:
              logger.debug(
                "Не удалось определить дату бронирования для триггера")
              continue
            logger.debug(f"Дата {date_type}: {booking_date}")

            if is_trigger_day == 0:
              logger.debug(
                f"Триггер сработал! {notification.trigger_days} дней относительно {date_type}")
              await send_notification(http_session, booking, notification, booking_date, date_type)
            else:
              logger.debug(
                f"Триггер не сработал, дата найденного бронирования {booking_date} не равна текущей дате")

  except Exception as e:
    logger.error(f"Ошибка при проверке триггеров: {str(e)}", exc_info=True)


def is_time_in_window(target_time: Optional[dt_time], current_time: datetime,
    window_minutes: int = 29) -> bool:
  """Проверяет совпадение времени с учетом окна"""
  logger.debug(
    f"Проверка временного окна: target_time={target_time}, current_time={current_time}")
  if target_time is None:
    logger.debug("Время триггера не задано - пропускаем проверку")
    return True

  target_datetime = datetime.combine(current_time.date(), target_time)
  window = timedelta(minutes=window_minutes)
  result = target_datetime - window <= current_time <= target_datetime + window
  logger.debug(f"Результат проверки временного окна: {result}")
  return result


from datetime import date, timedelta


def get_booking_date(booking: Booking, notification: Notification) -> tuple:
  """Возвращает дату для проверки триггера, вычисленную как текущая дата
  плюс/минус указанное количество дней (trigger_days), и тип даты"""
  logger.debug(
      f"Получение даты бронирования для колонки: {notification.trigger_column}, "
      f"триггер дней {notification.trigger_days}, "
      f"ИД бронирования {booking.id}"
  )

  # Получаем текущую дату
  is_trigger_day = 1
  today = date.today()
  target_date = today + timedelta(days=notification.trigger_days)

  if notification.trigger_column == 'Заезд':
    if booking.check_in == target_date:
      is_trigger_day = 0
    logger.debug(
        f"Используется текущая дата с корректировкой: {target_date} "
        f"(текущая: {today}), для сравнения с датой заезда: {booking.check_in}, is_trigger_day = {is_trigger_day}"
    )
    return is_trigger_day, target_date, "заезда"
  elif notification.trigger_column == 'Выезд':
    if booking.check_out == target_date:
      is_trigger_day = 0
    logger.debug(
        f"Используется текущая дата с корректировкой: {target_date} "
        f"(текущая: {today}), для сравнения с датой выезда: {booking.check_out}, is_trigger_day = {is_trigger_day}"
    )
    return is_trigger_day, target_date, "выезда"

  logger.debug("Неизвестный тип колонки триггера")
  return is_trigger_day, None, ""


async def send_notification(http_session, booking: Booking,
    notification: Notification, booking_date, date_type: str):
  """Формирует и отправляет уведомление"""
  logger.info(f"Подготовка уведомления для бронирования ID: {booking.id}")
  trigger_info = format_notification_message(booking, notification,
                                             booking_date, date_type)
  # Форматируем сообщение, заменяя {field_name} на значения из booking
  formatted_message = format_message_with_booking_data(notification.message, notification.notification_type,
                                                       booking)
  logger.debug(f"Сформированное сообщение:\n{formatted_message}")

  await send_telegram_message(http_session, trigger_info)
  await send_telegram_message(http_session, formatted_message)
  logger.info(f"Уведомление для бронирования ID: {booking.id} отправлено")


def format_message_with_booking_data(message: str, notification_type: str, booking: Booking) -> str:
  """Заменяет {field_name} в сообщении на значения из объекта Booking.
  Форматирует даты в дд.мм.уууу. Для типа 'Отправка планирование уборки'
  использует тайский календарь (+543 года)."""
  logger.debug(f"Форматирование сообщения с данными бронирования")
  if not message:
    logger.debug("Сообщение пустое - пропускаем форматирование")
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
      logger.debug(
        f"Замена плейсхолдера {placeholder} на значение: {field_value}")

      # Преобразуем даты в читаемый формат
      if isinstance(field_value, (datetime, date)):
        if notification_type == 'Отправка планирование уборки':
          # Для уведомлений об уборке используем тайский год
          thai_year = field_value.year + 543
          formatted_date = field_value.strftime(f'%d.%m.{thai_year}')
        else:
          # Для остальных случаев стандартный формат
          formatted_date = field_value.strftime('%d.%m.%Y')
        field_value = formatted_date
      elif field_value is None:
        field_value = ""

      # Заменяем плейсхолдер на значение
      formatted_message = formatted_message.replace(placeholder,
                                                  str(field_value))

  logger.debug(f"Результат форматирования:\n{formatted_message}")
  return formatted_message

async def send_telegram_message(http_session, message: str):
  """Асинхронно отправляет сообщение в несколько Telegram чатов"""
  logger.debug(f"Попытка отправки сообщения в Telegram")
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
      logger.debug(f"Отправка запроса к Telegram API: {url}")
      async with http_session.post(url, json=payload) as response:
        if response.status == 200:
          logger.info(f"Сообщение отправлено в чат {chat_id}")
        else:
          error = await response.json()
          logger.error(f"Ошибка при отправке в чат {chat_id}: {error}")
    except Exception as e:
      logger.error(f"Ошибка соединения при отправке в чат {chat_id}: {str(e)}")


def format_notification_message(booking: Booking, notification: Notification,
    booking_date, date_type: str) -> str:
  """Форматирует сообщение уведомления"""
  logger.debug("Форматирование информационного сообщения об уведомлении")
  trigger_type = "после" if notification.trigger_days < 0 else "до"
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


if __name__ == "__main__":
  # Тестовый вызов
  try:
    import asyncio

    logger.info("Ручной запуск проверки триггеров уведомлений")
    asyncio.run(check_notification_triggers())
    logger.info("Ручной вызов check_notification_triggers завершен успешно")
  except Exception as e:
    logger.error(f"Ошибка при ручном запуске: {e}", exc_info=True)