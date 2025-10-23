# view_dates.py
from datetime import date, timedelta
from typing import List, Tuple

from common.database import SessionLocal
from sqlalchemy import select
from telegram import Update

from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking

logger = setup_logger("view_dates")


async def view_dates_handler(update: Update, context):
  """Вывод всех свободных диапазонов дат в разрезе sheet_name"""
  with SessionLocal() as session:
    # Получаем все уникальные sheet_name
    sheet_names = session.execute(
        select(Booking.sheet_name).distinct()
    ).scalars().all()

    if not sheet_names:
      await update.message.reply_text("Нет данных о бронированиях.")
      return

    for sheet in sheet_names:
      # Получаем все бронирования для текущего sheet_name, отсортированные по дате заезда
      bookings = session.execute(
          select(Booking)
          .where(Booking.sheet_name == sheet)
          .order_by(Booking.check_in)
      ).scalars().all()

      # Формируем список занятых периодов
      booked_periods = [(b.check_in, b.check_out) for b in bookings if
                        b.check_in and b.check_out]

      # Находим свободные периоды
      free_periods = find_free_periods(booked_periods)

      # Формируем сообщение
      message = f"📅 <b>Свободные даты для {sheet}</b>\n\n"

      if not free_periods:
        message += "❌ Нет свободных периодов"
      else:
        message += "🆓 Свободно:\n"
        for start, end in free_periods:
          nights = (end - start).days
          message += (
            f"📅 С {start.strftime('%d.%m.%Y')} - По {end.strftime('%d.%m.%Y')}\n"
            f"🌙 {nights} ночей\n\n"
          )

      await update.message.reply_text(message, parse_mode='HTML')


def find_free_periods(booked_periods: List[Tuple[date, date]],
    start_date: date = date.today(),
    end_date: date = date.today() + timedelta(days=365)) -> List[
  Tuple[date, date]]:
  """
    Находит свободные периоды между занятыми датами.

    Args:
        booked_periods: Список кортежей (check_in, check_out)
        start_date: Дата начала поиска (по умолчанию сегодня)
        end_date: Дата окончания поиска (по умолчанию +1 год от сегодня)

    Returns:
        Список кортежей с начальной и конечной датами свободных периодов
    """
  if not booked_periods:
    return [(start_date, end_date)]

  # Сортируем периоды по дате заезда
  sorted_periods = sorted(booked_periods, key=lambda x: x[0])

  free_periods = []
  previous_end = start_date

  for period in sorted_periods:
    current_start, current_end = period

    # Если между предыдущим и текущим периодом есть промежуток
    if previous_end < current_start:
      free_periods.append((previous_end, current_start - timedelta(days=1)))

    # Обновляем previous_end до максимальной даты
    if current_end > previous_end:
      previous_end = current_end

  # Проверяем период после последнего бронирования
  if previous_end < end_date:
    free_periods.append((previous_end, end_date))

  return free_periods