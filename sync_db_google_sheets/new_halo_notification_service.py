from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from pathlib import Path
import asyncio

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


async def send_halo_notifications(title: str):
    """Отправляет уведомления о свободных датах в группы Telegram через ChannelMonitor"""
    logger.info(f"Запуск отправки уведомлений для объекта: {title}")
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

            # Получаем свободные даты для указанного объекта (исправленный запрос)
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

            # Остальной код остается без изменений
            # Получаем список изображений из папки, если она указана
            images = []
            if IMAGES_FOLDER and IMAGES_FOLDER.exists():
                images = list(IMAGES_FOLDER.glob('*.*'))
                images = [img for img in images if
                          img.suffix.lower() in ['.jpg', '.jpeg', '.png']]
                logger.info(f"Найдено {len(images)} изображений для отправки")

            # Создаем экземпляр ChannelMonitor
            monitor = ChannelMonitor()
            await monitor.client.start(monitor.phone)

            for group in groups:
                try:
                    # Получаем минимальный период для отправки из настроек группы
                    send_frequency = group.send_frequency if group.send_frequency is not None else 0

                    # Формируем список свободных дат с учетом send_frequency
                    free_dates = format_free_dates_with_frequency(
                        bookings, current_date, future_date, send_frequency)

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
                        f"{free_dates}\n\n"
                        "⚠️Есть и другие варианты, спрашивайте в ЛС."
                    )

                    # Проверяем, забанен ли пользователь в группе
                    # Улучшенный поиск группы
                    chat_entity = None
                    try:
                        # Попытка 1: Поиск по точному имени
                        try:
                            chat_entity = await monitor.client.get_entity(group.chat_name)
                        except ValueError:
                            # Попытка 2: Поиск среди текущих диалогов
                            async for dialog in monitor.client.iter_dialogs():
                                if dialog.name and dialog.name.lower() == group.chat_name.lower():
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
                            # Отправляем сообщение с изображениями
                            await monitor.client.send_message(
                                chat_entity,
                                message,
                                file=images
                            )
                            logger.info(
                                f"Сообщение с {len(images)} изображениями отправлено в группу {group.chat_name}")
                        else:
                            # Отправляем просто текстовое сообщение
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
        if 'monitor' in locals():
            await monitor.client.disconnect()


def format_free_dates_with_frequency(bookings: List[Booking], current_date,
                                    future_date, min_days: int) -> str:
    """Форматирует список свободных дат, исключая периоды короче min_days"""
    date_ranges = []
    prev_check_out = None
    current_range_start = None

    for booking in sorted(bookings,
                          key=lambda x: x.check_in or datetime.max.date()):
        # Если check_in None, считаем что дата свободна начиная с check_out
        if booking.check_in is None and booking.check_out:
            if current_range_start:
                # Проверяем длительность текущего периода перед добавлением
                duration = (prev_check_out - current_range_start).days + 1
                if duration >= min_days:
                    date_ranges.append(
                        format_date_range(current_range_start, prev_check_out))
                current_range_start = None

            # Период "и далее" всегда включаем
            date_ranges.append(f"с {booking.check_out.strftime('%d.%m.%y')} и далее")
            continue

        if not booking.check_in:
            continue

        # Если текущий check_in в будущем (после future_date), пропускаем
        if booking.check_in > future_date:
            continue

        # Если между предыдущим check_out и текущим check_in есть промежуток
        if prev_check_out and booking.check_in > prev_check_out + timedelta(days=1):
            if current_range_start:
                # Проверяем длительность текущего периода перед добавлением
                duration = (prev_check_out - current_range_start).days + 1
                if duration >= min_days:
                    date_ranges.append(
                        format_date_range(current_range_start, prev_check_out))
            current_range_start = booking.check_in
        elif not current_range_start:
            current_range_start = booking.check_in

        prev_check_out = booking.check_out if booking.check_out else booking.check_in

    # Проверяем последний диапазон
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
            banned_rights = participant.banned_rights
            if banned_rights and isinstance(banned_rights, ChatBannedRights):
                return banned_rights.view_messages
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке бана в чате {chat_id}: {str(e)}")
        return False


async def main():
    await send_halo_notifications("HALO Title")


if __name__ == "__main__":
    asyncio.run(main())