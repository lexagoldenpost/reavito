# Синхронизация таблицы бронирования
import json
import threading
from typing import Dict, Any, Union

import gspread
import numpy as np
import pandas as pd
from common.database import SessionLocal
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy import select

from chat_sync import process_chats_sheet
from common.config import Config
from common.logging_config import setup_logger
from google_sheets_to_channels_keywords import process_channels_keywords_sheet
from models import Booking
from sync_task import process_notifications_sheet

logger = setup_logger("sync_google_booking")

# Глобальная блокировка для синхронизации
sync_lock = threading.Lock()


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
  """Очищает и преобразует данные DataFrame"""
  column_mapping = {
    'ID': 'id',
    'Гость': 'guest',
    'Дата бронирования': 'booking_date',
    'Заезд': 'check_in',
    'Выезд': 'check_out',
    'Количество ночей': 'nights',
    'Сумма по месяцам': 'amount_by_month',
    'СуммаБатты': 'total_amount',
    'Аванс Батты/Рубли': 'deposit',
    'Доплата Батты/Рубли': 'balance',
    'Источник': 'source',
    'Дополнительные доплаты': 'additional_payments',
    'Расходы': 'expenses',
    'Оплата': 'payment_method',
    'Комментарий': 'comments',
    'телефон': 'phone',
    'дополнительный телефон': 'additional_phone',
    'Рейсы': 'flights'
  }

  existing_columns = [col for col in column_mapping.keys() if col in df.columns]
  df = df.rename(
      columns={k: v for k, v in column_mapping.items() if
               k in existing_columns})

  # Преобразуем даты и ID
  date_columns = ['booking_date', 'check_in', 'check_out']
  for col in date_columns:
    if col in df.columns:
      df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')

  if 'id' in df.columns:
    df['id'] = pd.to_numeric(df['id'], errors='coerce')

  # Заменяем NaN/NaT на None
  df = df.replace([np.nan, pd.NaT], None)

  return df


def calculate_nights(check_in, check_out):
  """Рассчитывает количество ночей между датами"""
  if pd.isna(check_in) or pd.isna(check_out):
    return None
  try:
    nights = (check_out - check_in).days
    return str(nights) if nights > 0 else None
  except Exception as e:
    logger.error(f"Ошибка расчета количества ночей: {e}")
    return None

def process_google_sheets_to_db(
          google_sheet_key: str = None,
          credentials_json: Union[Dict[str, Any], str] = None
  ) -> Dict[str, str]:
    """
    Основная функция синхронизации данных между Google Sheets и БД
    с автоматическим расчетом количества ночей и гарантированным заполнением ID
    """
    if Config.IS_SYNC_BOOKING == "false":
      logger.info(f"Не синхронизируем IS_SYNC_BOOKING: {Config.IS_SYNC_BOOKING}")
      return {
        "status": "success",
        "message": "Синхронизация отключена в настройках (IS_SYNC_BOOKING=false)"
      }

    if google_sheet_key is None:
      google_sheet_key = Config.BOOKING_SPREADSHEET_ID
    if credentials_json is None:
      credentials_json = Config.SERVICE_ACCOUNT_FILE

    with sync_lock:
      try:
        # Авторизация в Google Sheets API
        scope = [
          'https://spreadsheets.google.com/feeds',
          'https://www.googleapis.com/auth/drive'
        ]

        if isinstance(credentials_json, str):
          try:
            credentials_json = json.loads(credentials_json)
          except json.JSONDecodeError:
            logger.error("Неверный формат credentials_json")
            return {
              "status": "error",
              "message": "Неверный формат credentials_json"
            }

        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json, scope)
        client = gspread.authorize(creds)

        # Открываем таблицу
        spreadsheet = client.open_by_key(google_sheet_key)
        all_updates = []
        id_clear_updates = []

        # Обрабатываем каждый лист
        for sheet in spreadsheet.worksheets():
          sheet_name = sheet.title
          logger.info(f"Обработка листа: {sheet_name}")
          updates = []

          try:
            # Получаем все данные листа
            all_values = sheet.get_all_values()
            if len(all_values) < 1:
              logger.info(f"Лист {sheet_name} пуст, пропускаем")
              continue

            headers = all_values[0]
            df = pd.DataFrame(all_values[1:], columns=headers)

            # Убедимся, что столбец ID существует
            if 'ID' not in headers:
              logger.info(f"Добавляем столбец ID в лист {sheet_name}")
              sheet.add_cols(1)
              id_col_idx = len(headers) + 1
              sheet.update_cell(1, id_col_idx, 'ID')
              headers.append('ID')
              # Обновляем данные после добавления столбца
              all_values = sheet.get_all_values()
              headers = all_values[0]
              df = pd.DataFrame(all_values[1:], columns=headers)

            id_col_idx = headers.index('ID') + 1
            id_col_letter = gspread.utils.rowcol_to_a1(1, id_col_idx)[0]

            # Очищаем и преобразуем данные
            df = clean_data(df)
            df['sheet_name'] = sheet_name

            # Рассчитываем количество ночей для новых записей
            nights_updates = []
            if 'check_in' in df.columns and 'check_out' in df.columns:
              for idx, row in df.iterrows():
                row_num = idx + 2
                if pd.isna(row.get('nights')) and not pd.isna(row.get('check_in')) and not pd.isna(
                        row.get('check_out')):
                  nights = calculate_nights(row['check_in'], row['check_out'])
                  if nights:
                    cell = f"{gspread.utils.rowcol_to_a1(1, headers.index('Количество ночей') + 1)[0]}{row_num}"
                    nights_updates.append({
                      'range': cell,
                      'values': [[nights]]
                    })
                    df.at[idx, 'nights'] = nights

            # Применяем обновления количества ночей
            if nights_updates:
              try:
                sheet.batch_update(nights_updates)
                logger.info(f"Обновлено {len(nights_updates)} значений количества ночей в листе {sheet_name}")
              except Exception as e:
                logger.error(f"Ошибка при обновлении количества ночей: {e}")

            # Синхронизируем данные с БД
            with SessionLocal() as session:
              # Получаем существующие записи из БД
              existing_records = session.execute(
                select(Booking).where(Booking.sheet_name == sheet_name)
              ).scalars().all()

              existing_by_id = {r.id: r for r in existing_records}
              existing_by_key = {
                (r.sheet_name, r.guest, r.booking_date): r
                for r in existing_records
                if r.guest and r.booking_date
              }

              records_to_keep = set()

              # Обрабатываем каждую строку в таблице
              for idx, row in df.iterrows():
                row_num = idx + 2
                try:
                  row_id = row.get('id')
                  is_empty = is_row_empty(row, ['id', 'sheet_name'])

                  # Обработка пустых строк
                  if is_empty:
                    if row_id and row_id in existing_by_id:
                      session.delete(existing_by_id[row_id])
                      logger.info(f"Удалена запись с ID: {row_id} (пустая строка)")
                      updates.append({
                        'range': f"{id_col_letter}{row_num}",
                        'values': [[""]]
                      })
                    continue

                  # Пропускаем строки без гостя или даты бронирования
                  if pd.isna(row.get('guest')) or pd.isna(row.get('booking_date')):
                    continue

                  # Если ID нет в строке
                  if not row_id or str(row_id).strip() in ('', 'None'):
                    record_key = (sheet_name, row['guest'], row['booking_date'])

                    # Ищем существующую запись
                    if record_key in existing_by_key:
                      db_record = existing_by_key[record_key]
                      if has_changes(db_record, row):
                        update_record(db_record, row)
                        logger.info(f"Обновлена запись с ID: {db_record.id}")

                      # Добавляем ID в таблицу
                      updates.append({
                        'range': f"{id_col_letter}{row_num}",
                        'values': [[str(db_record.id)]]
                      })
                      records_to_keep.add(db_record.id)
                    else:
                      # Создаем новую запись
                      new_record = create_new_record(row)
                      session.add(new_record)
                      session.flush()

                      # Добавляем ID в таблицу
                      updates.append({
                        'range': f"{id_col_letter}{row_num}",
                        'values': [[str(new_record.id)]]
                      })
                      records_to_keep.add(new_record.id)
                      logger.info(f"Добавлена новая запись с ID: {new_record.id}")
                  else:
                    # Для строк с существующим ID
                    if row_id in existing_by_id:
                      db_record = existing_by_id[row_id]
                      if has_changes(db_record, row):
                        update_record(db_record, row)
                        logger.info(f"Обновлена запись с ID: {row_id}")
                      records_to_keep.add(row_id)
                    else:
                      # Создаем новую запись с существующим ID
                      new_record = create_new_record(row)
                      new_record.id = row_id
                      session.add(new_record)
                      session.flush()
                      records_to_keep.add(row_id)
                      logger.info(f"Добавлена новая запись с существующим ID: {row_id}")

                      # Обновляем ID в таблице (на случай если он был неверным)
                      updates.append({
                        'range': f"{id_col_letter}{row_num}",
                        'values': [[str(row_id)]]
                      })

                except Exception as e:
                  logger.error(f"Ошибка при обработке строки {row_num}: {str(e)}")
                  continue

              # Удаляем записи, которых нет в таблице
              for record in existing_records:
                if record.id not in records_to_keep:
                  session.delete(record)
                  logger.info(f"Удалена запись с ID: {record.id} (отсутствует в таблице)")

              session.commit()

            # Применяем обновления ID к текущему листу
            if updates:
              try:
                sheet.batch_update(updates)
                logger.info(f"Успешно обновлено {len(updates)} ID в листе {sheet_name}")
              except Exception as e:
                logger.error(f"Ошибка при обновлении ID в листе {sheet_name}: {str(e)}")

          except Exception as e:
            logger.error(f"Ошибка при обработке листа {sheet_name}: {str(e)}")
            continue

        logger.info("Синхронизация данных завершена")
        return {
          "status": "success",
          "message": "Синхронизация успешно завершена"
        }

      except Exception as e:
        logger.error(f"Ошибка при обработке Google таблицы: {str(e)}", exc_info=True)
        return {
          "status": "error",
          "message": f"Ошибка при синхронизации: {str(e)}"
        }

def is_row_empty(row, exclude_columns=None):
  exclude_columns = exclude_columns or []
  for col, value in row.items():
    if col in exclude_columns:
      continue
    if value is not None and str(value).strip() not in ('', 'None', 'null'):
      return False
  return True


def has_changes(db_record, row_data):
  for column in [
    'guest', 'booking_date', 'check_in', 'check_out', 'nights',
    'amount_by_month', 'total_amount', 'deposit', 'balance',
    'source', 'additional_payments', 'expenses', 'payment_method',
    'comments', 'phone', 'additional_phone', 'flights'
  ]:
    if column in row_data:
      db_value = getattr(db_record, column)
      sheet_value = row_data[column]

      if db_value != sheet_value:
        if pd.isna(db_value) and pd.isna(sheet_value):
          continue
        return True
  return False


def update_record(db_record, row_data):
  for column in [
    'guest', 'booking_date', 'check_in', 'check_out', 'nights',
    'amount_by_month', 'total_amount', 'deposit', 'balance',
    'source', 'additional_payments', 'expenses', 'payment_method',
    'comments', 'phone', 'additional_phone', 'flights'
  ]:
    if column in row_data:
      setattr(db_record, column, row_data[column])


def create_new_record(row_data):
  return Booking(
      sheet_name=row_data.get('sheet_name'),
      guest=row_data.get('guest'),
      booking_date=row_data.get('booking_date'),
      check_in=row_data.get('check_in'),
      check_out=row_data.get('check_out'),
      nights=row_data.get('nights'),
      amount_by_month=row_data.get('amount_by_month'),
      total_amount=row_data.get('total_amount'),
      deposit=row_data.get('deposit'),
      balance=row_data.get('balance'),
      source=row_data.get('source'),
      additional_payments=row_data.get('additional_payments'),
      expenses=row_data.get('expenses'),
      payment_method=row_data.get('payment_method'),
      comments=row_data.get('comments'),
      phone=row_data.get('phone'),
      additional_phone=row_data.get('additional_phone'),
      flights=row_data.get('flights')
  )


def update_single_record_in_google_sheet(
    record_id: int,
    sheet_name: str,
    google_sheet_key: str = None,
    credentials_json: Union[Dict[str, Any], str] = None
) -> Dict[str, str]:
  """
  Обновляет одну запись в Google таблице по ID записи

  Args:
      record_id: ID записи в БД
      sheet_name: Название листа в Google таблице
      google_sheet_key: Ключ Google таблицы (опционально)
      credentials_json: Данные авторизации (опционально)

  Returns:
      Словарь с результатом операции {'status': 'success'/'error', 'message': str}
  """
  if google_sheet_key is None:
    google_sheet_key = Config.BOOKING_SPREADSHEET_ID
  if credentials_json is None:
    credentials_json = Config.SERVICE_ACCOUNT_FILE

  with sync_lock:
    try:
      # Авторизация в Google Sheets API
      scope = ['https://spreadsheets.google.com/feeds',
               'https://www.googleapis.com/auth/drive']

      if isinstance(credentials_json, str):
        try:
          credentials_json = json.loads(credentials_json)
        except json.JSONDecodeError:
          logger.error("Неверный формат credentials_json")
          return {"status": "error",
                  "message": "Неверный формат credentials_json"}

      creds = ServiceAccountCredentials.from_json_keyfile_dict(
          credentials_json, scope)
      client = gspread.authorize(creds)

      # Открываем таблицу
      spreadsheet = client.open_by_key(google_sheet_key)

      # Получаем нужный лист
      try:
        worksheet = spreadsheet.worksheet(sheet_name)
      except gspread.exceptions.WorksheetNotFound:
        logger.error(f"Лист {sheet_name} не найден")
        return {"status": "error",
                "message": f"Лист {sheet_name} не найден"}

      # Получаем все данные листа
      all_values = worksheet.get_all_values()
      if len(all_values) < 1:
        return {"status": "error",
                "message": "Лист пустой"}

      headers = all_values[0]

      # Находим индекс столбца ID
      if 'ID' not in headers:
        return {"status": "error",
                "message": "Столбец ID не найден в листе"}

      id_col_idx = headers.index('ID') + 1

      # Ищем запись с нужным ID
      found_row = None
      for idx, row in enumerate(all_values[1:]):
        if len(row) >= id_col_idx and str(row[id_col_idx - 1]) == str(
            record_id):
          found_row = idx + 2  # +1 для заголовка, +1 для 0-based индекса
          break

      if not found_row:
        return {"status": "error",
                "message": f"Запись с ID {record_id} не найдена в листе {sheet_name}"}

      # Получаем данные из БД
      with SessionLocal() as session:
        booking = session.get(Booking, record_id)
        if not booking:
          return {"status": "error",
                  "message": f"Запись с ID {record_id} не найдена в БД"}

        # Подготавливаем данные для обновления
        update_data = {
          'ID': str(booking.id),
          'Гость': booking.guest,
          'Дата бронирования': booking.booking_date.strftime(
              '%d.%m.%Y') if booking.booking_date else '',
          'Заезд': booking.check_in.strftime(
              '%d.%m.%Y') if booking.check_in else '',
          'Выезд': booking.check_out.strftime(
              '%d.%m.%Y') if booking.check_out else '',
          'Количество ночей': str(booking.nights) if booking.nights else '',
          'Сумма по месяцам': booking.amount_by_month if booking.amount_by_month else '',
          'СуммаБатты': str(
              booking.total_amount) if booking.total_amount else '',
          'Аванс Батты/Рубли': booking.deposit if booking.deposit else '',
          'Доплата Батты/Рубли': booking.balance if booking.balance else '',
          'Источник': booking.source if booking.source else '',
          'Дополнительные доплаты': booking.additional_payments if booking.additional_payments else '',
          'Расходы': booking.expenses if booking.expenses else '',
          'Оплата': booking.payment_method if booking.payment_method else '',
          'Комментарий': booking.comments if booking.comments else '',
          'телефон': booking.phone if booking.phone else '',
          'дополнительный телефон': booking.additional_phone if booking.additional_phone else '',
          'Рейсы': booking.flights if booking.flights else ''
        }

        # Формируем список обновлений
        updates = []
        for col_name, value in update_data.items():
          if col_name in headers:
            col_idx = headers.index(col_name) + 1
            # Используем только адрес ячейки без указания листа
            cell = gspread.utils.rowcol_to_a1(found_row, col_idx)
            updates.append({
              'range': cell,  # Убираем название листа из range
              'values': [[value]]
            })

        # Применяем все обновления
        if updates:
          worksheet.batch_update(updates)

      logger.info(
          f"Успешно обновлена запись с ID {record_id} в листе {sheet_name}")
      return {"status": "success",
              "message": f"Запись с ID {record_id} успешно обновлена"}

    except Exception as e:
      logger.error(f"Ошибка при обновлении записи с ID {record_id}: {str(e)}",
                   exc_info=True)
      return {"status": "error",
              "message": f"Ошибка при обновлении записи: {str(e)}"}


async def sync_handler(update, context):
  """Обработчик для синхронизации таблиц"""
  try:
    logger.info("Начало синхронизации данных из Google Sheets в БД")

    # Вызываем функцию обработки Google Sheets
    result = process_google_sheets_to_db()

    # Add check for None result
    if result is None:
      logger.error("Функция process_google_sheets_to_db вернула None")
      await update.message.reply_text(
          "Ошибка: функция синхронизации вернула неожиданный результат")
      return

    # Проверяем статус ответа и отправляем соответствующее сообщение боту
    if result.get("status") == "success":
      logger.info("Синхронизация данных завершена успешно")
      await update.message.reply_text(
        "Синхронизация бронирований успешно завершена")
    else:
      error_msg = result.get("message", "Неизвестная ошибка при синхронизации")
      logger.error(f"Ошибка при синхронизации: {error_msg}")
      await update.message.reply_text(
        f"Ошибка при синхронизации бронирований: {error_msg}")

    # Вызываем функцию обработки Google Sheets
    result = process_notifications_sheet()
    # Проверяем статус ответа и отправляем соответствующее сообщение боту
    if result.get("status") == "success":
      logger.info("Синхронизация задач завершена успешно")
      await update.message.reply_text("Синхронизация задач успешно завершена")
    else:
      error_msg = result.get("message",
                             "Неизвестная ошибка при синхронизации")
      logger.error(f"Ошибка при синхронизации: {error_msg}")
      await update.message.reply_text(
          f"Ошибка при синхронизации задач: {error_msg}")

    # Вызываем функцию обработки Google Sheets
    result = process_chats_sheet()
    # Проверяем статус ответа и отправляем соответствующее сообщение боту
    if result.get("status") == "success":
      logger.info("Синхронизация чатов завершена успешно")
      await update.message.reply_text(
          "Синхронизация чатов успешно завершена")
    else:
      error_msg = result.get("message",
                             "Неизвестная ошибка при синхронизации")
      logger.error(f"Ошибка при синхронизации: {error_msg}")
      await update.message.reply_text(
          f"Ошибка при синхронизации чатов: {error_msg}")

    # Вызываем функцию обработки Google Sheets
    result = process_channels_keywords_sheet()
    # Проверяем статус ответа и отправляем соответствующее сообщение боту
    if result.get("status") == "success":
      logger.info("Синхронизация поиска по чатам завершена успешно")
      await update.message.reply_text(
          "Синхронизация поиска по чатам успешно завершена")
    else:
      error_msg = result.get("message",
                             "Неизвестная ошибка при синхронизации")
      logger.error(f"Ошибка при синхронизации: {error_msg}")
      await update.message.reply_text(
          f"Ошибка при синхронизации поиска по чатам: {error_msg}")

  except Exception as e:
    logger.error(f"Error in view_booking_handler: {e}")
    await update.message.reply_text(
      "Синхронизация: Произошла ошибка при обработке запроса")


if __name__ == '__main__':
  process_google_sheets_to_db()
