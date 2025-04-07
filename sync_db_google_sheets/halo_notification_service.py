from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path
import asyncio

from sqlalchemy import select, and_, or_
from telethon.sync import TelegramClient
from telethon.tl.types import Channel, ChatBannedRights

from common.config import Config
from common.database import SessionLocal
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Booking, Chat

logger = setup_logger("halo_notification_service")

# Конфигурация из переменных окружения
TELEGRAM_API_ID = Config.TELEGRAM_API_SEARCH_ID
TELEGRAM_API_HASH = Config.TELEGRAM_API_SEARCH_HASH
TELEGRAM_SESSION_NAME = 'channel_monitor_session' #Config.TELEGRAM_SEARCH_PHONE+"_"+Config.TELEGRAM_SESSION_NAME
IMAGES_FOLDER = Path(Config.IMAGES_FOLDER) if Config.IMAGES_FOLDER else None


async def send_halo_notifications(title: str):
    """Отправляет уведомления о свободных датах в группы Telegram по их названию"""
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

            # Получаем свободные даты для указанного объекта
            bookings = session.execute(
                select(Booking).where(
                    and_(
                        Booking.sheet_name == title,
                        Booking.check_out >= current_date,
                        or_(
                            Booking.check_in <= future_date,
                            Booking.check_in.is_(None)
                        )
                    )
                ).order_by(Booking.check_in)
            ).scalars().all()

            if not bookings:
                logger.info(f"Нет свободных дат для объекта {title}")
                return

            # Формируем список свободных дат
            free_dates = format_free_dates(bookings, current_date, future_date)
            if not free_dates:
                logger.info(f"Нет свободных дат в указанном диапазоне для {title}")
                return

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

            # Получаем список изображений из папки, если она указана
            images = []
            if IMAGES_FOLDER and IMAGES_FOLDER.exists():
                images = list(IMAGES_FOLDER.glob('*.*'))
                images = [img for img in images if img.suffix.lower() in ['.jpg', '.jpeg', '.png']]
                logger.info(f"Найдено {len(images)} изображений для отправки")

            # Подключаемся к Telegram
            async with TelegramClient(TELEGRAM_SESSION_NAME, TELEGRAM_API_ID,
                                      TELEGRAM_API_HASH) as client:
                for group in groups:
                    try:
                        # Вариант 1: Поиск по точному имени
                        try:
                            chat_entity = await client.get_entity(
                                group.chat_name)
                        except ValueError:
                            # Вариант 2: Поиск среди текущих диалогов
                            found = False
                            async for dialog in client.iter_dialogs():
                                if dialog.name == group.chat_name:
                                    chat_entity = dialog.entity
                                    found = True
                                    break

                            if not found:
                                raise ValueError(
                                    f"Группа '{group.chat_name}' не найдена в диалогах")

                        # Проверка бана
                        if await is_user_banned(client, chat_entity.id):
                            logger.info(
                                f"Пользователь забанен в группе {group.chat_name}")
                            continue

                        # Отправка сообщения
                        if group.accepts_images and images:
                            # Отправляем сообщение с изображениями
                            await client.send_message(
                                chat_entity,
                                message,
                                file=images
                            )
                            logger.info(
                                f"Сообщение с {len(images)} изображениями отправлено в группу {group.chat_name}")
                        else:
                            # Отправляем просто текстовое сообщение
                            await client.send_message(chat_entity, message)
                            logger.info(
                                f"Текстовое сообщение отправлено в группу {group.chat_name}")

                    except Exception as e:
                        logger.error(
                            f"Ошибка работы с группой {group.chat_name}: {str(e)}")
                        continue

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {str(e)}", exc_info=True)


async def is_user_banned(client: TelegramClient, chat_id: int) -> bool:
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


def format_free_dates(bookings: List[Booking], current_date, future_date) -> str:
    """Форматирует список свободных дат в читаемый вид"""
    date_ranges = []
    prev_check_out = None
    current_range_start = None

    for booking in sorted(bookings, key=lambda x: x.check_in or datetime.max.date()):
        # Если check_in None, считаем что дата свободна начиная с check_out
        if booking.check_in is None and booking.check_out:
            if current_range_start:
                date_ranges.append(format_date_range(current_range_start, prev_check_out))
                current_range_start = None
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
                date_ranges.append(format_date_range(current_range_start, prev_check_out))
            current_range_start = booking.check_in
        elif not current_range_start:
            current_range_start = booking.check_in

        prev_check_out = booking.check_out if booking.check_out else booking.check_in

    # Добавляем последний диапазон, если он есть
    if current_range_start and prev_check_out:
        date_ranges.append(format_date_range(current_range_start, prev_check_out))

    return "\n".join(date_ranges) if date_ranges else ""


def format_date_range(start_date, end_date) -> str:
    """Форматирует диапазон дат в строку"""
    return f"{start_date.strftime('%d.%m.%y')}-{end_date.strftime('%d.%m.%y')}"


async def main():
    await send_halo_notifications("HALO Title")


if __name__ == "__main__":
    asyncio.run(main())