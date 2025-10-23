import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from common.database import SessionLocal
from sqlalchemy import select, and_, or_

from channel_monitor import ChannelMonitor
from common.config import Config
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking

logger = setup_logger("new_halo_notification_service")

# Конфигурация из переменных окружения
IMAGES_FOLDER = Path(Config.IMAGES_FOLDER) if Config.IMAGES_FOLDER else None


async def log_booking_periods(bookings: List[Booking],
    start_date: datetime.date, end_date: datetime.date, min_nights: int = 0) -> \
List[Tuple[datetime.date, datetime.date, int]]:
    """Логирует информацию о занятых и свободных периодах с учетом ночевок и возвращает список свободных периодов с min_nights и более"""
    # Сортируем бронирования по дате заезда
    sorted_bookings = sorted(
        [b for b in bookings if b.check_in is not None],
        key=lambda x: x.check_in
    )

    # Находим минимальную дату check_in после end_date (если есть)
    min_check_in_after_period = None
    for booking in sorted_bookings:
        if booking.check_in and booking.check_in > end_date:
            if min_check_in_after_period is None or booking.check_in < min_check_in_after_period:
                min_check_in_after_period = booking.check_in

    # Добавляем фиктивное бронирование для конца периода
    if min_check_in_after_period is not None:
        sorted_bookings.append(
            Booking(check_in=min_check_in_after_period, check_out=None))
    else:
        sorted_bookings.append(
            Booking(check_in=end_date + timedelta(days=1), check_out=None))

    prev_check_out = start_date
    periods = []
    free_periods = []

    for booking in sorted_bookings:
        # Проверяем свободный период между предыдущим check_out и текущим check_in
        if booking.check_in and prev_check_out < booking.check_in:
            # Количество ночевок = количество дней между датами + 1 ночь для свободных, так корректнее
            free_nights = (booking.check_in - prev_check_out).days + 1
            if free_nights > 0:
                period_info = {
                    'type': 'free',
                    'start': prev_check_out - timedelta(
                        days=1) if prev_check_out != datetime.now().date() else prev_check_out,
                    'end': booking.check_in,
                    'nights': free_nights
                }
                periods.append(period_info)
                if free_nights >= min_nights:
                    free_periods.append(
                        (period_info['start'], period_info['end'], period_info['nights']))

        # Добавляем занятый период
        if booking.check_in and booking.check_out:
            # Количество ночевок = (check_out - check_in).days
            busy_nights = (booking.check_out - booking.check_in).days
            period_info = {
                'type': 'busy',
                'start': booking.check_in,
                'end': booking.check_out,
                'nights': busy_nights
            }
            periods.append(period_info)
            prev_check_out = booking.check_out + timedelta(days=1)
        elif booking.check_in:  # Для записей без check_out
            prev_check_out = booking.check_in

    # Группируем периоды по месяцам для удобного отображения
    months = defaultdict(list)
    for period in periods:
        month_key = period['start'].strftime('%Y-%m')
        months[month_key].append(period)

    # Логируем информацию по месяцам
    for month, month_periods in sorted(months.items()):
        logger.info(f"\nМесяц: {month}")
        for period in month_periods:
            if period['type'] == 'free':
                logger.info(
                    f"  СВОБОДНО: {period['start'].strftime('%d.%m')}-{period['end'].strftime('%d.%m')} "
                    f"({period['nights']} ночей)")
            else:
                logger.info(
                    f"  ЗАНЯТО:  {period['start'].strftime('%d.%m')}-{period['end'].strftime('%d.%m')} "
                    f"({period['nights']} ночей)")

    # Логируем информацию о периодах "и далее"
    for booking in bookings:
        if booking.check_in is None and booking.check_out:
            logger.info(
                f"\nСВОБОДНО С: {booking.check_out.strftime('%d.%m.%Y')} и далее")

    return free_periods


def format_free_dates_with_frequency(bookings: List[Booking], current_date,
    future_date, min_days: int) -> str:
    """Форматирует список свободных дат, исключая периоды короче min_days"""
    date_ranges = []
    prev_check_out = None
    current_range_start = None

    for booking in sorted(bookings,
                          key=lambda x: x.check_in or datetime.max.date()):
        if booking.check_in is None and booking.check_out:
            if current_range_start:
                duration = (prev_check_out - current_range_start).days + 1
                if duration >= min_days:
                    date_ranges.append(
                        format_date_range(current_range_start, prev_check_out))
                current_range_start = None

            date_ranges.append(f"с {booking.check_out.strftime('%d.%m.%y')} и далее")
            continue

        if not booking.check_in:
            continue

        if booking.check_in > future_date:
            continue

        if prev_check_out and booking.check_in > prev_check_out + timedelta(days=1):
            if current_range_start:
                duration = (prev_check_out - current_range_start).days + 1
                if duration >= min_days:
                    date_ranges.append(
                        format_date_range(current_range_start, prev_check_out))
            current_range_start = booking.check_in
        elif not current_range_start:
            current_range_start = booking.check_in

        prev_check_out = booking.check_out if booking.check_out else booking.check_in

    if current_range_start and prev_check_out:
        duration = (prev_check_out - current_range_start).days + 1
        if duration >= min_days:
            date_ranges.append(format_date_range(current_range_start, prev_check_out))

    return "\n".join(date_ranges) if date_ranges else ""


def format_date_range(start_date, end_date) -> str:
    """Форматирует диапазон дат в строку"""
    return f"{start_date.strftime('%d.%m.%y')}-{end_date.strftime('%d.%m.%y')}"


async def send_to_specific_chat(
    chat_id: str,
    title: str,
    images: Optional[List[Path]] = None
) -> bool:
    """Отправляет уведомление в конкретный чат/группу по ID и возвращает результат отправки

    Args:
        chat_id (str): ID чата/группы в Telegram (может начинаться с минуса)
        title (str): Название объекта для поиска в базе данных
        images (Optional[List[Path]]): Список путей к изображениям для отправки

    Returns:
        bool: True если сообщение отправлено успешно, False в случае ошибки
    """
    logger.info(f"Запуск отправки в чат {chat_id} для объекта: {title}")

    current_date = datetime.now().date()
    future_date = current_date + timedelta(days=60)  # 2 месяца вперед

    monitor = None
    try:
        with SessionLocal() as session:
            # Получаем свободные даты для указанного объекта
            bookings = session.execute(
                select(Booking)
                .where(
                    and_(
                        Booking.sheet_name == title,
                        Booking.check_out >= current_date,
                        or_(
                            Booking.check_in <= future_date,
                            Booking.check_in.is_(None)
                        )
                    )
                )
                .order_by(Booking.check_in)  # Moved outside the where clause
            ).scalars().all()

            if not bookings:
                logger.info(f"Нет свободных дат для объекта {title}")
                return False

            # Получаем список изображений из папки, если она указана
            if images is None and IMAGES_FOLDER and IMAGES_FOLDER.exists():
                images = list(IMAGES_FOLDER.glob('*.*'))
                images = [img for img in images if
                          img.suffix.lower() in ['.jpg', '.jpeg', '.png']]
                logger.info(f"Найдено {len(images)} изображений для отправки")

            # Получаем свободные периоды (используем минимальный период 0 дней)
            free_periods = await log_booking_periods(bookings, current_date,
                                                   future_date, 0)

            # Формируем список свободных дат
            free_dates = []
            for start, end, nights in free_periods:
                free_dates.append(
                    f"{start.strftime('%d.%m.%y')}-{end.strftime('%d.%m.%y')} ({nights} ночей)")

            # Добавляем периоды "и далее"
            for booking in bookings:
                if booking.check_in is None and booking.check_out:
                    free_dates.append(
                        f"с {booking.check_out.strftime('%d.%m.%y')} и далее")

            if not free_dates:
                logger.info(f"Нет свободных дат для объекта {title}")
                return False

            # Формируем сообщение
            message = (
                f"Аренда квартиры в новом комплексе {title} в 400м от пляжа Най Янг\n"
                "10 минут езды от аэропорта!\n"
                "🏡 1BR 36м2, 3й этаж, вид на бассейн\n\n"
                "🗝️Собственник!\n\n"
                "СВОБОДНЫЕ ДЛЯ БРОНИРОВАНИЯ ДАТЫ :\n\n"
                f"{'\n'.join(free_dates)}\n\n"
                "⚠️Есть и другие варианты, спрашивайте в ЛС."
            )

            # Реальная отправка
            monitor = ChannelMonitor()
            if not await monitor.initialize():
                logger.error("Failed to initialize ChannelMonitor")
                return False

            # Получаем клиента
            client = monitor.get_client()
            if client is None:
                logger.error("Failed to get Telegram client")
                return False

            # Преобразуем chat_id в int (удаляем минус если есть)
            try:
                chat_id_int = int(chat_id)
            except ValueError:
                logger.error(f"Некорректный chat_id: {chat_id}")
                return False

            # Отправка сообщения
            try:
                if images:
                    await client.send_message(
                        chat_id_int,
                        message,
                        file=images
                    )
                    logger.info(
                        f"Сообщение с {len(images)} изображениями отправлено в чат {chat_id}")
                else:
                    await client.send_message(chat_id_int, message)
                    logger.info(
                        f"Текстовое сообщение отправлено в чат {chat_id}")
                return True
            except Exception as e:
                logger.error(
                    f"Ошибка отправки сообщения в чат {chat_id}: {str(e)}")
                return False

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {str(e)}",
                     exc_info=True)
        return False


async def main():
    parser = argparse.ArgumentParser(
        description='Отправка уведомлений о свободных датах')
    parser.add_argument('chat_id', type=str, help='ID чата для отправки (может начинаться с минуса)')
    parser.add_argument('title', type=str,
                      help='Название объекта для поиска в базе данных')
    args = parser.parse_args()

    result = await send_to_specific_chat(args.chat_id, args.title)
    print(f"Результат отправки: {'Успешно' if result else 'Ошибка'}")


if __name__ == "__main__":
    asyncio.run(main())