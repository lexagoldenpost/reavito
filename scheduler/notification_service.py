# main_tg_bot/notification_service.py

import csv
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import aiohttp

from common.config import Config
from common.logging_config import setup_logger
# Используем booking_objects для точного соответствия объект ↔ файл
from main_tg_bot.booking_objects import BOOKING_SHEETS, get_booking_sheet, PROJECT_ROOT
from telega.tg_notifier import send_message

logger = setup_logger("notification_service")
TELEGRAM_CHAT_IDS = Config.TELEGRAM_CHAT_NOTIFICATION_ID

# --- Загрузка задач из other/tasks.csv ---
def load_tasks_from_csv(csv_file: str = "tasks.csv") -> List[Dict[str, Any]]:
    project_root = PROJECT_ROOT
    csv_path = project_root / Config.TASK_DATA_DIR / csv_file
    tasks = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            tasks = [row for row in reader]
        logger.info(f"✅ Загружено {len(tasks)} задач из {csv_path}")
        for i, task in enumerate(tasks, 1):
            logger.debug(
                f"  [{i}] {task.get('Оповещение')} | объект={task.get('Триггер по объекту')} | "
                f"столбец={task.get('Триггер по столбцу')} | "
                f"смещение={task.get('Тригер срок в днях (минус срок до, без срок после)')}"
            )
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки задач из {csv_path}: {e}")
    return tasks


# --- Загрузка бронирований по объекту с использованием booking_objects ---
def load_object_data_from_csv(object_name: str) -> List[Dict[str, Any]]:
    # Ищем объект по точному имени листа (например, 'Halo JU701 двушка')
    sheet_obj = get_booking_sheet(object_name)
    if not sheet_obj:
        logger.warning(f"⚠️ Неизвестный объект: '{object_name}'. Доступные: {list(BOOKING_SHEETS.keys())}")
        return []

    csv_path = Path(sheet_obj.filepath)
    if not csv_path.exists():
        logger.warning(f"⚠️ Файл не найден: {csv_path}")
        return []

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        logger.info(f"✅ Загружено {len(data)} записей для объекта '{object_name}' из {csv_path}")
        return data
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных объекта {object_name}: {e}")
        return []


# --- Остальные функции без изменений (логика дат, триггеров и т.д.) ---
def parse_date(date_str: str) -> Optional[date]:
    if not date_str or date_str.strip() == '':
        return None
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    logger.warning(f"⚠️ Не удалось распарсить дату: '{date_str}'")
    return None


def enrich_booking_with_dates(booking: Dict[str, Any]) -> Dict[str, Any]:
    booking['_check_in'] = parse_date(booking.get('Заезд', ''))
    booking['_check_out'] = parse_date(booking.get('Выезд', ''))
    return booking


def get_event_date(booking: Dict[str, Any], trigger_column: str) -> Optional[date]:
    if trigger_column == 'Заезд':
        return booking.get('_check_in')
    elif trigger_column == 'Выезд':
        return booking.get('_check_out')
    return None


def should_trigger_notification(
    notification: Dict[str, Any], booking: Dict[str, Any], today: date
) -> bool:
    guest = booking.get('Гость', 'N/A')
    obj = booking.get('sheet_name', 'N/A')
    notif_name = notification.get('Оповещение', 'N/A')

    trigger_obj = notification.get('Триггер по объекту')
    if booking.get('sheet_name') != trigger_obj:
        logger.debug(f"[SKIP] ❌ Объект не совпадает: бронь='{obj}', триггер='{trigger_obj}' → гость={guest}")
        return False

    trigger_col = notification.get('Триггер по столбцу')
    if trigger_col not in ('Заезд', 'Выезд'):
        logger.debug(f"[SKIP] ❌ Неверный столбец триггера: '{trigger_col}' → {notif_name}")
        return False

    event_date = get_event_date(booking, trigger_col)
    if not event_date:
        logger.debug(f"[SKIP] ❌ Нет даты события ({trigger_col}) для брони → гость={guest}")
        return False

    raw_offset = notification.get('Тригер срок в днях (минус срок до, без срок после)', '0')
    try:
        offset_days = int(raw_offset)
    except (ValueError, TypeError):
        logger.debug(f"[SKIP] ❌ Неверное значение смещения: '{raw_offset}' → {notif_name}")
        return False

    trigger_date = event_date - timedelta(days=offset_days)
    matches = (trigger_date == today)

    logger.debug(
        f"[CHECK] {'✅ MATCH' if matches else '❌ NO'} | гость={guest} | уведомление='{notif_name}' | "
        f"событие={event_date} ({trigger_col}) | смещение={offset_days} | "
        f"триггер={trigger_date} | сегодня={today}"
    )

    return matches


def format_message_with_booking_data(
    message: str,
    notification_type: str,
    booking: Dict[str, Any],
    current_date: date
) -> str:
    if not message:
        return message

    formatted = message

    for field, value in booking.items():
        placeholder = f"{{{field}}}"
        if placeholder in formatted:
            if field in ('Заезд', 'Выезд'):
                parsed = booking.get(f'_{field.lower()}') or parse_date(value)
                if parsed:
                    if notification_type == 'Отправка планирование уборки':
                        thai_year = parsed.year + 543
                        formatted_date = parsed.strftime(f'%d.%m.{thai_year}')
                    else:
                        formatted_date = parsed.strftime('%d.%m.%Y')
                    formatted = formatted.replace(placeholder, formatted_date)
            else:
                formatted = formatted.replace(placeholder, str(value) if value else '')

    if '{thai_year}' in formatted:
        thai_year = current_date.year + 543
        formatted = formatted.replace('{thai_year}', str(thai_year))

    return formatted


def format_trigger_info(booking: Dict[str, Any], notification: Dict[str, Any], current_date: date) -> str:
    try:
        offset_days = int(notification.get('Тригер срок в днях (минус срок до, без срок после)', 0))
    except (ValueError, TypeError):
        offset_days = 0

    trigger_col = notification.get('Триггер по столбцу', '')
    event_type = "заезда" if trigger_col == 'Заезд' else "выезда"
    direction = "после" if offset_days < 0 else "до"

    event_date = get_event_date(booking, trigger_col)

    check_in_str = booking['_check_in'].strftime('%d.%m.%Y') if booking.get('_check_in') else '—'
    check_out_str = booking['_check_out'].strftime('%d.%m.%Y') if booking.get('_check_out') else '—'

    return (
        "🔔 <b>Сработало уведомление</b> 🔔\n"
        f"🏠 <b>Объект:</b> {notification.get('Триггер по объекту', 'Не указан')}\n"
        f"👤 <b>Гость:</b> {booking.get('Гость', 'Не указан')}\n"
        f"📅 <b>Даты бронирования:</b> {check_in_str} – {check_out_str}\n"
        f"⏰ <b>Тип уведомления:</b> {notification.get('Оповещение', 'Не указан')}\n"
        f"📆 <b>Дата {event_type}:</b> {event_date.strftime('%d.%m.%Y') if event_date else '—'}\n"
        f"📌 <b>Триггер по:</b> {event_type}\n"
        f"⏳ <b>Дней {direction} {event_type}:</b> {abs(offset_days)}\n\n"
        "<b>Сообщение:</b>"
    )


async def send_notification(http_session, booking: Dict[str, Any], notification: Dict[str, Any], current_date: date):
    logger.info(f"📤 Отправка уведомления: {notification['Оповещение']} для {booking.get('Гость', 'N/A')}")

    trigger_info = format_trigger_info(booking, notification, current_date)
    formatted_message = format_message_with_booking_data(
        notification.get('Сообщение', ''),
        notification.get('Оповещение', ''),
        booking,
        current_date
    )

    logger.debug(f"📝 Текст сообщения:\n{formatted_message}")

    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            await send_message(http_session, chat_id, trigger_info)
            await send_message(http_session, chat_id, formatted_message)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в чат {chat_id}: {e}")

    logger.info(f"✅ Уведомление успешно отправлено для гостя: {booking.get('Гость', 'N/A')}")


async def check_notification_triggers():
    logger.info("🚀 Запуск проверки триггеров уведомлений")
    today = datetime.now().date()
    logger.info(f"📅 Текущая дата: {today}")

    notifications = load_tasks_from_csv()
    if not notifications:
        logger.info("📭 Нет задач для обработки")
        return

    objects = {
        n.get('Триггер по объекту')
        for n in notifications
        if n.get('Триггер по объекту')
    }
    logger.info(f"🏢 Объекты для обработки: {sorted(objects)}")

    all_bookings = []
    for obj in objects:
        raw_bookings = load_object_data_from_csv(obj)
        for b in raw_bookings:
            b['sheet_name'] = obj
            enriched = enrich_booking_with_dates(b)
            all_bookings.append(enriched)
            logger.debug(
                f"📥 Бронь: гость={enriched.get('Гость')} | объект={obj} | "
                f"заезд={enriched.get('_check_in')} | выезд={enriched.get('_check_out')}"
            )

    if not all_bookings:
        logger.info("📭 Нет бронирований для проверки")
        return

    logger.info(f"🔍 Начинаю проверку {len(all_bookings)} бронирований на {len(notifications)} триггеров")

    async with aiohttp.ClientSession() as session:
        for booking in all_bookings:
            for notification in notifications:
                if should_trigger_notification(notification, booking, today):
                    await send_notification(session, booking, notification, today)

    logger.info("🏁 Проверка триггеров завершена")


if __name__ == "__main__":
    try:
        import asyncio
        logger.info("🔧 Ручной запуск проверки триггеров")
        asyncio.run(check_notification_triggers())
        logger.info("✅ Ручной запуск завершён успешно")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка при ручном запуске: {e}", exc_info=True)