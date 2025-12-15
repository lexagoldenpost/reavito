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
  if not date_str or str(date_str).strip().lower() in ('', 'nan', 'none',
                                                       'null'):
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

  # Сохраняем оригинальное имя объекта для проверки
  original_object_name = object_display_name
  logger.info(
      f"✏️ [handle_edit_booking] Оригинальное имя объекта: {original_object_name}")

  # --- Сразу отправляем "обрабатывается" ---
  if init_chat_id:
    try:
      async with aiohttp.ClientSession() as session:
        await send_message(session, init_chat_id,
                           f"✏️ Изменение бронирования {guest_name} обрабатывается...")
        logger.info(
            f"📢 Уведомление 'обрабатывается' отправлено в чат {init_chat_id}")
    except Exception as e:
      logger.warning(
          f"Не удалось отправить начальное уведомление в Telegram: {e}")

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
        raise ValueError(
            f"❌ Неизвестный объект: '{object_display_name}'. Доступные: {available}")

    csv_filepath = booking_sheet.filepath
    sheet_name_for_sync = booking_sheet.sheet_name

    # Определяем, является ли это booking_other
    is_booking_other = object_display_name.lower() == 'booking_other' or csv_filepath.name == 'booking_other.csv'
    logger.info(
      f"✏️ [handle_edit_booking] Это booking_other: {is_booking_other}")

    if not csv_filepath.exists():
      raise FileNotFoundError(
          f"❌ Файл бронирований для объекта '{object_display_name}' не найден.")

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
    # Пропускаем проверку пересечений для объекта "booking_other"
    logger.info(
        f"✏️ [handle_edit_booking] Проверяем объект для пересечений: original_object_name='{original_object_name}', object_display_name='{object_display_name}'")

    if not is_booking_other:
      logger.info("✏️ [handle_edit_booking] Выполняем проверку пересечений дат")
      existing_df = df[~mask].copy()
      overlaps = []
      for _, row in existing_df.iterrows():
        existing_check_in = parse_date(row['Заезд'])
        existing_check_out = parse_date(row['Выезд'])

        # Пропускаем записи с некорректными или отсутствующими датами
        if existing_check_in is None or existing_check_out is None:
          continue

        # Проверка пересечения интервалов
        if not (
            check_out <= existing_check_in or check_in >= existing_check_out):
          overlaps.append((row['Гость'], row['Заезд'], row['Выезд']))

      if overlaps:
        overlap_list = "\n".join(
            [f" • {g} ({ci} – {co})" for g, ci, co in overlaps])
        raise ValueError(
            "❌ Невозможно обновить бронирование: обнаружены пересечения по датам:\n"
            f"{overlap_list}\n\n"
            "Пожалуйста, выберите другие даты."
        )
    else:
      logger.info(
          "✏️ [handle_edit_booking] Пропускаем проверку пересечений для booking_other")

    # --- Обновление данных (базовые поля для всех объектов) ---
    update_fields = {
      'Гость': data.get('guest', original_row.get('Гость', '')),
      'Дата бронирования': data.get('booking_date',
                                    original_row.get('Дата бронирования', '')),
      'Заезд': check_in_str,
      'Выезд': check_out_str,
      'Количество ночей': data.get('nights',
                                   original_row.get('Количество ночей', '')),
      'СуммаБатты': data.get('total_sum', original_row.get('СуммаБатты', '')),
      'Аванс Батты/Рубли': data.get('advance',
                                    original_row.get('Аванс Батты/Рубли', '')),
      'Доплата Батты/Рубли': data.get('additional_payment',
                                      original_row.get('Доплата Батты/Рубли',
                                                       '')),
      'Источник': data.get('source', original_row.get('Источник', '')),
      'Дополнительные доплаты': data.get('extra_charges', original_row.get(
          'Дополнительные доплаты', '')),
      'Расходы': data.get('expenses', original_row.get('Расходы', '')),
      'Оплата': data.get('payment_method', original_row.get('Оплата', '')),
      'Комментарий': data.get('comment', original_row.get('Комментарий', '')),
      'телефон': data.get('phone', original_row.get('телефон', '')),
      'дополнительный телефон': data.get('extra_phone', original_row.get(
          'дополнительный телефон', '')),
      'Рейсы': data.get('flights', original_row.get('Рейсы', '')),
      '_sync_id': sync_id  # не меняется
    }

    # --- Дополнительные поля для booking_other ---
    if is_booking_other:
      # Обработка данных хозяина
      condo_name = data.get('condo_name', '')
      apartment_number = data.get('apartment_number', '')
      owner_name = data.get('owner_name', '')

      # Если поля не переданы в data, берем из original_row
      if not condo_name and 'Название кондо' in original_row:
        condo_name = original_row['Название кондо']
      if not apartment_number and 'Номер апарта' in original_row:
        apartment_number = original_row['Номер апарта']
      if not owner_name and 'Хозяин' in original_row:
        owner_name = original_row['Хозяин']

      update_fields['Название кондо'] = condo_name
      update_fields['Номер апарта'] = apartment_number
      update_fields['Хозяин'] = owner_name

      # Обработка комиссии
      commission = data.get('commission', '0')
      if commission == '':
        commission = '0'

      # Если комиссия не передана, берем из original_row
      if commission == '0' and 'Комиссия' in original_row:
        commission = original_row['Комиссия']

      update_fields['Комиссия'] = commission

      logger.info(f"✏️ [handle_edit_booking] Данные для booking_other:")
      logger.info(f"    Название кондо: {condo_name}")
      logger.info(f"    Номер апарта: {apartment_number}")
      logger.info(f"    Хозяин: {owner_name}")
      logger.info(f"    Комиссия: {commission}")

    # Проверяем, что все колонки существуют в DataFrame
    # Если нет - добавляем их
    for column_name in update_fields.keys():
      if column_name not in df.columns:
        logger.warning(
          f"⚠️ Колонка '{column_name}' отсутствует в CSV, добавляем её")
        df[column_name] = ''

    # Обновляем данные
    for column_name, value in update_fields.items():
      df.loc[mask, column_name] = value

    try:
      df.to_csv(csv_filepath, index=False, encoding='utf-8')
      logger.info(f"✅ Бронирование с _sync_id={sync_id} обновлено")
      logger.info(f"✅ Файл сохранен: {csv_filepath}")

      # Логируем обновленные данные для отладки
      logger.info(f"✏️ [handle_edit_booking] Обновлены данные:")
      for key, value in update_fields.items():
        logger.info(f"    {key}: {value}")

    except Exception as save_error:
      logger.error(f"❌ Ошибка при сохранении CSV: {save_error}")
      raise RuntimeError("Ошибка при сохранении изменений в файл.")

    # --- Синхронизация с Google Таблицей ---
    try:
      sync_manager = GoogleSheetsCSVSync()
      sync_success = sync_manager.sync_sheet(sheet_name=sheet_name_for_sync,
                                             direction='csv_to_google')
      if not sync_success:
        raise RuntimeError("Синхронизация завершилась со статусом False")
    except Exception as sync_error:
      logger.error(f"❌ Ошибка при синхронизации: {sync_error}")
      raise RuntimeError("Проблема с синхронизацией в Google Таблицу.")

    # --- УСПЕХ ---
    if init_chat_id:
      async with aiohttp.ClientSession() as session:
        success_msg = f"✅ Бронирование гостя «{guest_name}» успешно обновлено!"
        if is_booking_other:
          success_msg = f"✅ Бронирование {guest_name} в booking_other успешно обновлено!"
        await send_message(session, init_chat_id, success_msg)
        logger.info(
            f"✅ Уведомление об успешном редактировании отправлено в чат {init_chat_id}")

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