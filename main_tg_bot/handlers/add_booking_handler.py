# main_tg_bot/handlers/add_booking_handler.py

import uuid
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
from telega.tg_notifier import send_message
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
import aiohttp

logger = setup_logger("add_booking_handler")


async def handle_add_booking(data: Dict[str, Any], filename: str):
    logger.info("📄 [handle_add_booking] Начало обработки бронирования")
    logger.info(f"📄 [handle_add_booking] Имя файла: {filename}")
    logger.info(f"📄 [handle_add_booking] Данные договора:")
    for key, value in data.items():
        logger.info(f"    {key}: {value}")

    init_chat_id: Optional[str] = data.get('init_chat_id')
    guest_name: str = data.get('guest', 'Гость').strip() or 'Гость'

    # --- Сразу отправляем "обрабатывается" ---
    if init_chat_id:
        try:
            async with aiohttp.ClientSession() as session:
                message = f"✅ Ваше бронирование, {guest_name}, обрабатывается..."
                await send_message(session, init_chat_id, message)
                logger.info(f"📢 Уведомление 'обрабатывается' отправлено в чат {init_chat_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить начальное уведомление в Telegram: {e}")

    try:
        # --- Валидация дат ---
        check_in_str = data.get('check_in', '').strip()
        check_out_str = data.get('check_out', '').strip()

        if not check_in_str or not check_out_str:
            error_msg = "❌ В бронировании должны быть указаны даты заезда и выезда."
            logger.error(error_msg)
            if init_chat_id:
                async with aiohttp.ClientSession() as session:
                    await send_message(session, init_chat_id, error_msg)
            return

        def parse_date(date_str: str):
            for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
                try:
                    return pd.to_datetime(date_str, format=fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Неверный формат даты: {date_str}")

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

        # --- Определение объекта недвижимости ---
        object_display_name = data.get('object', '').strip()
        if not object_display_name:
            logger.error("❌ Не указан объект недвижимости")
            if init_chat_id:
                async with aiohttp.ClientSession() as session:
                    await send_message(session, init_chat_id, "❌ Не указан объект недвижимости.")
            return

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

        # --- Проверка пересечений с существующими бронированиями ---
        existing_df = pd.DataFrame()
        if csv_filepath.exists():
            existing_df = pd.read_csv(csv_filepath, dtype=str).fillna('')

            overlaps = []
            for _, row in existing_df.iterrows():
                try:
                    # Пропускаем, если поля пустые
                    if not row['Заезд'].strip() or not row['Выезд'].strip():
                        continue

                    existing_check_in = parse_date(row['Заезд'])
                    existing_check_out = parse_date(row['Выезд'])

                    # Дополнительная проверка на None (если парсинг провалился)
                    if existing_check_in is None or existing_check_out is None:
                        continue

                    # Проверяем пересечение диапазонов дат
                    if not (check_out <= existing_check_in or check_in >= existing_check_out):
                        overlaps.append((row['Гость'], row['Заезд'], row['Выезд']))

                except Exception as e:
                    logger.warning(f"Пропущена строка из-за ошибки парсинга дат: {row.get('Гость', 'N/A')} | {e}")
                    continue  # Игнорируем повреждённые строки

            if overlaps:
                overlap_list = "\n".join([f" • {g} ({ci} – {co})" for g, ci, co in overlaps])
                error_msg = (
                    "❌ Невозможно создать бронирование: обнаружены пересечения по датам:\n"
                    f"{overlap_list}\n\n"
                    "Пожалуйста, выберите другие даты."
                )
                logger.error("Обнаружены пересекающиеся бронирования")
                if init_chat_id:
                    async with aiohttp.ClientSession() as session:
                        await send_message(session, init_chat_id, error_msg)
                return

        # --- Сохранение бронирования ---
        booking_uid = str(uuid.uuid4())
        booking_data = {
            'Гость': data.get('guest', ''),
            'Дата бронирования': data.get('booking_date', ''),
            'Заезд': check_in_str,
            'Выезд': check_out_str,
            'Количество ночей': data.get('nights', ''),
            'СуммаБатты': data.get('total_sum', ''),
            'Аванс Батты/Рубли': data.get('advance', ''),
            'Доплата Батты/Рубли': data.get('additional_payment', ''),
            'Источник': data.get('source', ''),
            'Дополнительные доплаты': data.get('extra_charges', ''),
            'Расходы': data.get('expenses', ''),
            'Оплата': data.get('payment_method', ''),
            'Комментарий': data.get('comment', ''),
            'телефон': data.get('phone', ''),
            'дополнительный телефон': data.get('extra_phone', ''),
            'Рейсы': data.get('flights', ''),
            '_sync_id': booking_uid
        }

        new_booking_df = pd.DataFrame([booking_data])

        try:
            if csv_filepath.exists():
                updated_df = pd.concat([existing_df, new_booking_df], ignore_index=True)
                updated_df.to_csv(csv_filepath, index=False, encoding='utf-8')
            else:
                new_booking_df.to_csv(csv_filepath, index=False, encoding='utf-8')
            logger.info(f"✅ Бронирование сохранено с UUID: {booking_uid}")
        except Exception as save_error:
            logger.error(f"❌ Ошибка при сохранении CSV: {save_error}")
            if init_chat_id:
                async with aiohttp.ClientSession() as session:
                    await send_message(
                        session,
                        init_chat_id,
                        "❌ Произошла ошибка при сохранении бронирования. Пожалуйста, повторите попытку или свяжитесь с поддержкой."
                    )
            return

        # --- Синхронизация с Google Таблицей ---
        try:
            sync_manager = GoogleSheetsCSVSync()
            sync_success = sync_manager.sync_sheet(sheet_name=sheet_name_for_sync, direction='csv_to_google')
            if not sync_success:
                raise RuntimeError("Синхронизация завершилась со статусом False")
        except Exception as sync_error:
            logger.error(f"❌ Ошибка при синхронизации листа '{sheet_name_for_sync}': {sync_error}")
            if init_chat_id:
                async with aiohttp.ClientSession() as session:
                    await send_message(
                        session,
                        init_chat_id,
                        "⚠️ Бронирование сохранено, но возникла проблема с синхронизацией в Google Таблицу. Администратор уже уведомлён."
                    )
            return

        # --- УСПЕХ: отправляем финальное подтверждение ---
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                success_msg = "✅ Бронирование успешно добавлено!"
                await send_message(session, init_chat_id, success_msg)
                logger.info(f"✅ Уведомление об успешном добавлении отправлено в чат {init_chat_id}")

        logger.info("📄 [handle_add_booking] Обработка бронирования завершена успешно")

    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при обработке бронирования: {e}")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(
                    session,
                    init_chat_id,
                    "❌ Произошла непредвиденная ошибка при обработке бронирования. Пожалуйста, обратитесь к администратору."
                )