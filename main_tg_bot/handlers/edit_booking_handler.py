# main_tg_bot/handlers/edit_booking_handler.py

import pandas as pd
from typing import Any, Dict, Optional

from common.logging_config import setup_logger
from main_tg_bot.booking_objects import (
    BOOKING_SHEETS,
    SHEET_TO_FILENAME,
    get_booking_sheet,
)
from telega.tg_notifier import send_message
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
import aiohttp

logger = setup_logger("edit_booking_handler")


def parse_date(date_str: str):
    """Безопасный парсинг даты. Возвращает datetime.date или None."""
    if not date_str or str(date_str).strip().lower() in ('', 'nan', 'none', 'null'):
        return None
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            dt = pd.to_datetime(date_str, format=fmt, errors='coerce')
            if pd.isna(dt):
                continue
            return dt.date()
        except Exception:
            continue
    return None


async def handle_edit_booking(data: Dict[str, Any], filename: str):
    logger.info("✏️ [handle_edit_booking] Начало редактирования бронирования")
    logger.info(f"✏️ [handle_edit_booking] Имя файла: {filename}")
    for key, value in data.items():
        logger.info(f"    {key}: {value}")

    init_chat_id: Optional[str] = data.get('init_chat_id')
    sync_id: str = data.get('_sync_id', '').strip()
    object_display_name: str = data.get('object', '').strip()
    guest_name: str = data.get('guest', 'Гость').strip() or 'Гость'

    # --- Сразу отправляем "обрабатывается" ---
    if init_chat_id:
        try:
            async with aiohttp.ClientSession() as session:
                await send_message(session, init_chat_id, f"✏️ Изменение бронирования {guest_name} обрабатывается...")
                logger.info(f"📢 Уведомление 'обрабатывается' отправлено в чат {init_chat_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить начальное уведомление в Telegram: {e}")

    try:
        if not sync_id:
            raise ValueError("❌ Не указан идентификатор бронирования (_sync_id).")

        if not object_display_name:
            raise ValueError("❌ Не указан объект недвижимости.")

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
                raise ValueError(f"❌ Неизвестный объект: '{object_display_name}'. Доступные: {available}")

        csv_filepath = booking_sheet.filepath
        sheet_name_for_sync = booking_sheet.sheet_name

        if not csv_filepath.exists():
            raise FileNotFoundError(f"❌ Файл бронирований для объекта '{object_display_name}' не найден.")

        try:
            df = pd.read_csv(csv_filepath, dtype=str).fillna('')
        except Exception as e:
            logger.error(f"❌ Ошибка при чтении CSV: {e}")
            raise RuntimeError("Не удалось прочитать файл бронирований.")

        if '_sync_id' not in df.columns:
            raise ValueError("❌ В файле отсутствует колонка '_sync_id'.")

        # --- Поиск записи ---
        mask = df['_sync_id'] == sync_id
        if not mask.any():
            raise ValueError(f"❌ Бронирование с _sync_id={sync_id} не найдено.")

        original_row = df[mask].iloc[0].copy()
        guest_name = original_row.get('Гость', 'Гость')

        # --- Валидация дат (если обновляются) ---
        check_in_str = data.get('check_in', original_row['Заезд']).strip()
        check_out_str = data.get('check_out', original_row['Выезд']).strip()

        check_in = parse_date(check_in_str)
        check_out = parse_date(check_out_str)

        if check_in is None or check_out is None:
            raise ValueError("❌ Неверный формат даты заезда или выезда.")

        if check_out <= check_in:
            raise ValueError("❌ Дата выезда должна быть позже даты заезда.")

        # --- Проверка пересечений (кроме самой себя) ---
        existing_df = df[~mask].copy()
        overlaps = []
        for _, row in existing_df.iterrows():
            existing_check_in = parse_date(row['Заезд'])
            existing_check_out = parse_date(row['Выезд'])

            # Пропускаем записи с некорректными или отсутствующими датами
            if existing_check_in is None or existing_check_out is None:
                continue

            # Проверка пересечения интервалов
            if not (check_out <= existing_check_in or check_in >= existing_check_out):
                overlaps.append((row['Гость'], row['Заезд'], row['Выезд']))

        if overlaps:
            overlap_list = "\n".join([f" • {g} ({ci} – {co})" for g, ci, co in overlaps])
            raise ValueError(
                "❌ Невозможно обновить бронирование: обнаружены пересечения по датам:\n"
                f"{overlap_list}\n\n"
                "Пожалуйста, выберите другие даты."
            )

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
            logger.error(f"❌ Ошибка при сохранении CSV: {save_error}")
            raise RuntimeError("Ошибка при сохранении изменений в файл.")

        # --- Синхронизация с Google Таблицей ---
        try:
            sync_manager = GoogleSheetsCSVSync()
            sync_success = sync_manager.sync_sheet(sheet_name=sheet_name_for_sync, direction='csv_to_google')
            if not sync_success:
                raise RuntimeError("Синхронизация завершилась со статусом False")
        except Exception as sync_error:
            logger.error(f"❌ Ошибка при синхронизации: {sync_error}")
            raise RuntimeError("Проблема с синхронизацией в Google Таблицу.")

        # --- УСПЕХ ---
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                success_msg = f"✅ Бронирование гостя «{guest_name}» успешно обновлено!"
                await send_message(session, init_chat_id, success_msg)
                logger.info(f"✅ Уведомление об успешном редактировании отправлено в чат {init_chat_id}")

        logger.info("✏️ [handle_edit_booking] Редактирование завершено успешно")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Ошибка при редактировании бронирования: {error_msg}")
        if init_chat_id:
            async with aiohttp.ClientSession() as session:
                await send_message(
                    session,
                    init_chat_id,
                    "❌ Произошла ошибка при обновлении бронирования. Пожалуйста, повторите попытку или обратитесь к администратору."
                )