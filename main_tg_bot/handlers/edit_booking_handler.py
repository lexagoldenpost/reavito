# main_tg_bot/handlers/edit_booking_handler.py

import pandas as pd
from pathlib import Path
from typing import Any, Dict, Optional

from common.logging_config import setup_logger
from main_tg_bot.booking_objects import (
    BOOKING_DIR,
    BOOKING_SHEETS,
    SHEET_TO_FILENAME,
    get_booking_sheet,
)
from main_tg_bot.sender.tg_notifier import send_message
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
import aiohttp

logger = setup_logger("edit_booking_handler")


def parse_date(date_str: str):
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return pd.to_datetime(date_str, format=fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Неверный формат даты: {date_str}")


async def handle_edit_booking(data: Dict[str, Any], filename: str):
    logger.info("✏️ [handle_edit_booking] Начало редактирования бронирования")
    logger.info(f"✏️ [handle_edit_booking] Имя файла: {filename}")
    for key, value in data.items():
        logger.info(f"    {key}: {value}")

    init_chat_id: Optional[str] = data.get('init_chat_id')
    sync_id: str = data.get('_sync_id', '').strip()
    object_display_name: str = data.get('object', '').strip()

    if not sync_id:
        error_msg = "❌ Не указан идентификатор бронирования (_sync_id)."
        logger.error(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    if not object_display_name:
        error_msg = "❌ Не указан объект недвижимости."
        logger.error(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    # --- Определение файла бронирования ---
    booking_sheet = get_booking_sheet(object_display_name)
    if booking_sheet is None:
        reverse_filename_to_sheet = {
            filename: sheet_name
            for sheet_name, filename in SHEET_TO_FILENAME.items()
        }
        possible_filename = f"{object_display_name.lower().replace(' ', '_')}.csv"
        if possible_filename in reverse_filename_to_sheet:
            object_display_name = reverse_filename_to_sheet[possible_filename]
            booking_sheet = get_booking_sheet(object_display_name)

        if booking_sheet is None:
            available = ', '.join(BOOKING_SHEETS.keys())
            error_msg = f"❌ Неизвестный объект: '{object_display_name}'. Доступные: {available}"
            logger.error(error_msg)
            if init_chat_id:
                async with aiohttp.ClientSession() as session:
                    await send_message(session, init_chat_id, error_msg)
            return

    csv_filepath = booking_sheet.filepath
    sheet_name_for_sync = booking_sheet.sheet_name

    if not csv_filepath.exists():
        error_msg = f"❌ Файл бронирований для объекта '{object_display_name}' не найден."
        logger.error(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    try:
        df = pd.read_csv(csv_filepath, dtype=str).fillna('')
    except Exception as e:
        logger.error(f"❌ Ошибка при чтении CSV: {e}")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(
                    session,
                    init_chat_id,
                    "❌ Не удалось прочитать файл бронирований. Обратитесь к администратору."
                )
        return

    if '_sync_id' not in df.columns:
        error_msg = "❌ В файле отсутствует колонка '_sync_id'."
        logger.error(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    # --- Поиск записи ---
    mask = df['_sync_id'] == sync_id
    if not mask.any():
        error_msg = f"❌ Бронирование с _sync_id={sync_id} не найдено."
        logger.warning(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    original_row = df[mask].iloc[0].copy()
    guest_name = original_row.get('Гость', 'Гость')

    # --- Валидация дат (если обновляются) ---
    check_in_str = data.get('check_in', original_row['Заезд']).strip()
    check_out_str = data.get('check_out', original_row['Выезд']).strip()

    try:
        check_in = parse_date(check_in_str)
        check_out = parse_date(check_out_str)
    except ValueError as ve:
        error_msg = f"❌ Неверный формат даты: {ve}"
        logger.error(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    if check_out <= check_in:
        error_msg = "❌ Дата выезда должна быть позже даты заезда."
        logger.error(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    # --- Проверка пересечений (кроме самой себя) ---
    existing_df = df[~mask].copy()
    overlaps = []
    for _, row in existing_df.iterrows():
        try:
            existing_check_in = parse_date(row['Заезд'])
            existing_check_out = parse_date(row['Выезд'])
        except Exception:
            continue

        if not (check_out <= existing_check_in or check_in >= existing_check_out):
            overlaps.append((row['Гость'], row['Заезд'], row['Выезд']))

    if overlaps:
        overlap_list = "\n".join([f" • {g} ({ci} – {co})" for g, ci, co in overlaps])
        error_msg = (
            "❌ Невозможно обновить бронирование: обнаружены пересечения по датам:\n"
            f"{overlap_list}\n\n"
            "Пожалуйста, выберите другие даты."
        )
        logger.error("Обнаружены пересекающиеся бронирования при редактировании")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    # --- Обновление данных ---
    update_fields = {
        'Гость': data.get('guest', original_row['Гость']),
        'Дата бронирования': data.get('booking_date', original_row['Дата бронирования']),
        'Заезд': check_in_str,
        'Выезд': check_out_str,
        'Количество ночей': data.get('nights', original_row['Количество ночей']),
        'СуммаБатты': data.get('total_sum', original_row['СуммаБатты']),
        'Аванс Батты/Рубли': data.get('advance', original_row['Аванс Батты/Рубли']),
        'Доплата Батты/Рубли': data.get('additional_payment', original_row['Доплата Батты/Рубли']),
        'Источник': data.get('source', original_row['Источник']),
        'Дополнительные доплаты': data.get('extra_charges', original_row['Дополнительные доплаты']),
        'Расходы': data.get('expenses', original_row['Расходы']),
        'Оплата': data.get('payment_method', original_row['Оплата']),
        'Комментарий': data.get('comment', original_row['Комментарий']),
        'телефон': data.get('phone', original_row['телефон']),
        'дополнительный телефон': data.get('extra_phone', original_row['дополнительный телефон']),
        'Рейсы': data.get('flights', original_row['Рейсы']),
        '_sync_id': sync_id  # не меняется
    }

    df.loc[mask, list(update_fields.keys())] = list(update_fields.values())

    try:
        df.to_csv(csv_filepath, index=False, encoding='utf-8')
        logger.info(f"✅ Бронирование с _sync_id={sync_id} обновлено")
    except Exception as save_error:
        logger.error(f"❌ Ошибка при сохранении CSV после редактирования: {save_error}")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(
                    session,
                    init_chat_id,
                    "❌ Ошибка при обновлении бронирования. Повторите попытку или обратитесь к администратору."
                )
        return

    # --- Синхронизация с Google Таблицей ---
    try:
        sync_manager = GoogleSheetsCSVSync()
        sync_success = sync_manager.sync_sheet(sheet_name=sheet_name_for_sync, direction='csv_to_google')
        if not sync_success:
            raise RuntimeError("Синхронизация завершилась со статусом False")
    except Exception as sync_error:
        logger.error(f"❌ Ошибка при синхронизации после редактирования: {sync_error}")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(
                    session,
                    init_chat_id,
                    "⚠️ Бронирование обновлено локально, но возникла проблема с синхронизацией в Google Таблицу. Администратор уведомлён."
                )
        return

    # --- УСПЕХ ---
    if init_chat_id:
        async with aiohttp.ClientSession() as session:
            success_msg = f"✅ Бронирование гостя «{guest_name}» успешно обновлено!"
            await send_message(session, init_chat_id, success_msg)
            logger.info(f"✅ Уведомление об успешном редактировании отправлено в чат {init_chat_id}")

    logger.info("✏️ [handle_edit_booking] Редактирование завершено успешно")