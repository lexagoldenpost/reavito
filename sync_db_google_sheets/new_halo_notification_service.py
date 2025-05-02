from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from pathlib import Path
import asyncio
import argparse

from sqlalchemy import select, and_, or_
from telethon.tl.types import Channel, ChatBannedRights

from common.config import Config
from common.database import SessionLocal
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking, Chat
from channel_monitor import ChannelMonitor

logger = setup_logger("new_halo_notification_service")

# Конфигурация из переменных окружения
IMAGES_FOLDER = Path(Config.IMAGES_FOLDER) if Config.IMAGES_FOLDER else None


async def send_halo_notifications(title: str, dry_run: bool = False):
    """Отправляет уведомления о свободных датах в группы Telegram через ChannelMonitor

    Args:
        title (str): Название объекта для поиска в базе данных
        dry_run (bool): Если True - только проверяет данные без реальной отправки
    """
    logger.info(f"Запуск отправки уведомлений для объекта: {title} (режим {'dry run' if dry_run else 'реальный'})")
    current_date = datetime.now().date()
    future_date = current_date + timedelta(days=60)  # 2 месяца вперед

    try:
        with SessionLocal() as session:
            # Получаем все группы чатов (где указано название группы)
            groups = session.execute(
                select(Chat).where(Chat.chat_name.is_not(None))
            ).scalars().all()

            if not groups:
                logger.info("Нет групп для отправки уведомлений")
                return

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
                .order_by(Booking.check_in)
            ).scalars().all()

            if not bookings:
                logger.info(f"Нет свободных дат для объекта {title}")
                return

            # Получаем список изображений из папки, если она указана
            images = []
            if IMAGES_FOLDER and IMAGES_FOLDER.exists():
                images = list(IMAGES_FOLDER.glob('*.*'))
                images = [img for img in images if
                          img.suffix.lower() in ['.jpg', '.jpeg', '.png']]
                logger.info(f"Найдено {len(images)} изображений для отправки")

            # В режиме dry_run не инициализируем клиент Telegram
            monitor = None
            if not dry_run:
                monitor = ChannelMonitor()
                await monitor.client.start(monitor.phone)

            for group in groups:
                try:
                    # Получаем минимальный период для отправки из настроек группы
                    send_frequency = group.send_frequency if group.send_frequency is not None else 0

                    # Получаем свободные периоды с учетом минимального количества ночей
                    free_periods = await log_booking_periods(bookings, current_date, future_date, send_frequency)

                    # Формируем список свободных дат
                    free_dates = []
                    for start, end, nights in free_periods:
                        free_dates.append(f"{start.strftime('%d.%m.%y')}-{end.strftime('%d.%m.%y')} ({nights} ночей)")

                    # Добавляем периоды "и далее"
                    for booking in bookings:
                        if booking.check_in is None and booking.check_out:
                            free_dates.append(f"с {booking.check_out.strftime('%d.%m.%y')} и далее")

                    if not free_dates:
                        logger.info(
                            f"Пропускаем группу {group.chat_name} - нет подходящих периодов "
                            f"(минимальная длительность {send_frequency} дней)")
                        continue

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

                    if dry_run:
                        # В режиме dry run только логируем что было бы отправлено
                        logger.info(f"DRY RUN: Сообщение для {group.chat_name}:\n{message}")
                        if group.accepts_images and images:
                            logger.info(f"DRY RUN: Приложено {len(images)} изображений")
                        continue

                    # Реальная отправка
                    chat_entity = None
                    try:
                        # Попытка 1: Поиск по точному имени
                        try:
                            chat_entity = await monitor.client.get_entity(group.chat_name)
                        except ValueError:
                            # Попытка 2: Поиск среди текущих диалогов
                            async for dialog in monitor.client.iter_dialogs():
                                if dialog.name and dialog.name.lower() == group.chat_name.lower() or str(
                                        dialog.id) == group.chat_name:
                                    chat_entity = dialog.entity
                                    break

                            if not chat_entity:
                                logger.error(f"Группа '{group.chat_name}' не найдена в диалогах")
                                continue

                        # Проверка бана
                        if await is_user_banned(monitor.client, chat_entity.id):
                            logger.info(f"Пользователь забанен в группе {group.chat_name}")
                            continue

                    except Exception as e:
                        logger.error(f"Ошибка получения информации о группе {group.chat_name}: {str(e)}")
                        continue

                    # Отправляем сообщение через ChannelMonitor
                    try:
                        if group.accepts_images and images:
                            await monitor.client.send_message(
                                chat_entity,
                                message,
                                file=images
                            )
                            logger.info(
                                f"Сообщение с {len(images)} изображениями отправлено в группу {group.chat_name}")
                        else:
                            await monitor.client.send_message(chat_entity, message)
                            logger.info(
                                f"Текстовое сообщение отправлено в группу {group.chat_name}")
                    except Exception as e:
                        logger.error(
                            f"Ошибка отправки сообщения в группу {group.chat_name}: {str(e)}")

                except Exception as e:
                    logger.error(
                        f"Ошибка работы с группой {group.chat_name}: {str(e)}")
                    continue

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {str(e)}", exc_info=True)
    finally:
        if monitor and not dry_run:
            await monitor.client.disconnect()


async def log_booking_periods(bookings: List[Booking], start_date: datetime.date, end_date: datetime.date, min_nights: int = 0) -> List[Tuple[datetime.date, datetime.date, int]]:
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
        sorted_bookings.append(Booking(check_in=min_check_in_after_period, check_out=None))
    else:
        sorted_bookings.append(Booking(check_in=end_date + timedelta(days=1), check_out=None))

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
                    'start': prev_check_out - timedelta(days=1) if prev_check_out != datetime.now().date() else prev_check_out,
                    'end': booking.check_in,
                    'nights': free_nights
                }
                periods.append(period_info)
                if free_nights >= min_nights:
                    free_periods.append((period_info['start'], period_info['end'], period_info['nights']))

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


async def is_user_banned(client, chat_id: int) -> bool:
    """Проверяет, забанен ли пользователь в чате"""
    try:
        chat = await client.get_entity(chat_id)
        if isinstance(chat, Channel):
            participant = await client.get_permissions(chat, 'me')
            if hasattr(participant, 'banned_rights') and participant.banned_rights:
                if isinstance(participant.banned_rights, ChatBannedRights):
                    return participant.banned_rights.view_messages
            elif hasattr(participant, 'kicked'):
                return participant.kicked
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке бана в чате {chat_id}: {str(e)}")
        return False


async def send_to_specific_chat(
    chat_id: str,
    title: str,
    dry_run: bool = False,
    images: Optional[List[Path]] = None
):
    """Отправляет уведомление в конкретный чат/группу по ID

    Args:
        chat_id (int): ID чата/группы в Telegram
        title (str): Название объекта для поиска в базе данных
        dry_run (bool): Если True - только проверяет данные без реальной отправки
        images (Optional[List[Path]]): Список путей к изображениям для отправки
    """
    logger.info(
        f"Запуск отправки в конкретный чат {chat_id} для объекта: {title} "
        f"(режим {'dry run' if dry_run else 'реальный'})")

    current_date = datetime.now().date()
    future_date = current_date + timedelta(days=60)  # 2 месяца вперед

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
                .order_by(Booking.check_in)
            ).scalars().all()

            if not bookings:
                logger.info(f"Нет свободных дат для объекта {title}")
                return

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
                return

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

            if dry_run:
                # В режиме dry run только логируем что было бы отправлено
                logger.info(
                    f"DRY RUN: Сообщение для чата {chat_id}:\n{message}")
                if images:
                    logger.info(f"DRY RUN: Приложено {len(images)} изображений")
                return

            # Реальная отправка
            monitor = ChannelMonitor()
            try:
                await monitor.client.start(monitor.phone)

                # Проверка бана
                if await is_user_banned(monitor.client, chat_id):
                    logger.info(f"Пользователь забанен в чате {chat_id}")
                    return

                # Отправка сообщения
                try:
                    if images:
                        await monitor.client.send_message(
                            chat_id,
                            message,
                            file=images
                        )
                        logger.info(
                            f"Сообщение с {len(images)} изображениями отправлено в чат {chat_id}")
                    else:
                        await monitor.client.send_message(chat_id, message)
                        logger.info(
                            f"Текстовое сообщение отправлено в чат {chat_id}")
                except Exception as e:
                    logger.error(
                        f"Ошибка отправки сообщения в чат {chat_id}: {str(e)}")

            finally:
                await monitor.client.disconnect()

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {str(e)}",
                     exc_info=True)

async def main():
    parser = argparse.ArgumentParser(description='Отправка уведомлений о свободных датах')
    parser.add_argument('title', type=str, help='Название объекта для поиска в базе данных')
    parser.add_argument('--dry-run', action='store_true', help='Режим тестирования без реальной отправки')
    args = parser.parse_args()

    await send_halo_notifications(args.title, args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())

# Реальная отправка
#await send_to_specific_chat(123456789, "HALO Title")

# Тестовый режим
#await send_to_specific_chat(123456789, "HALO Title", dry_run=True)
 # Основные изменения:
#
# Добавлен параметр dry_run в функцию send_halo_notifications
#
# В режиме dry run:
#
# Не инициализируется клиент Telegram
#
# Не выполняются реальные отправки сообщений
#
# Логируется информация о том, что было бы отправлено
#
# Добавлена обработка аргументов командной строки через argparse:
#
# Обязательный аргумент title - название объекта
#
# Опциональный флаг --dry-run для активации тестового режима
#
# Теперь скрипт можно запускать двумя способами:
#
# Реальная отправка:
#
# bash
# python script.py "HALO Title"
# Тестовый режим (без отправки):
#
# bash
# python script.py "HALO Title" --dry-run
# В тестовом режиме скрипт проверит все данные, найдет чаты и сформирует сообщения, но не будет выполнять реальные отправки в Telegram.