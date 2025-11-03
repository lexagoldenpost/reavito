# main_tg_bot/handlers/delete_booking_handler.py

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

logger = setup_logger("delete_booking_handler")


async def handle_delete_booking(data: Dict[str, Any], filename: str):
    logger.info("🗑️ [handle_delete_booking] Начало удаления бронирования")
    logger.info(f"🗑️ [handle_delete_booking] Имя файла: {filename}")
    logger.info(f"🗑️ [handle_delete_booking] Данные:")
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

    # --- Поиск и удаление записи ---
    mask = df['_sync_id'] == sync_id
    if not mask.any():
        error_msg = f"❌ Бронирование с _sync_id={sync_id} не найдено."
        logger.warning(error_msg)
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, error_msg)
        return

    deleted_row = df[mask].iloc[0]
    guest_name = deleted_row.get('Гость', 'Гость')

    df = df[~mask].reset_index(drop=True)

    try:
        df.to_csv(csv_filepath, index=False, encoding='utf-8')
        logger.info(f"✅ Бронирование с _sync_id={sync_id} удалено")
    except Exception as save_error:
        logger.error(f"❌ Ошибка при сохранении CSV после удаления: {save_error}")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(
                    session,
                    init_chat_id,
                    "❌ Ошибка при удалении бронирования. Повторите попытку или обратитесь к администратору."
                )
        return

    # --- Синхронизация с Google Таблицей ---
    try:
        sync_manager = GoogleSheetsCSVSync()
        sync_success = sync_manager.sync_sheet(sheet_name=sheet_name_for_sync, direction='csv_to_google')
        if not sync_success:
            raise RuntimeError("Синхронизация завершилась со статусом False")
    except Exception as sync_error:
        logger.error(f"❌ Ошибка при синхронизации после удаления: {sync_error}")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(
                    session,
                    init_chat_id,
                    "⚠️ Бронирование удалено локально, но возникла проблема с синхронизацией в Google Таблицу. Администратор уведомлён."
                )
        return

    # --- УСПЕХ ---
    if init_chat_id:
        async with aiohttp.ClientSession() as session:
            success_msg = f"✅ Бронирование гостя «{guest_name}» успешно удалено!"
            await send_message(session, init_chat_id, success_msg)
            logger.info(f"✅ Уведомление об успешном удалении отправлено в чат {init_chat_id}")

    logger.info("🗑️ [handle_delete_booking] Удаление завершено успешно")