import pandas as pd
from sqlalchemy import select, delete
from common.database import engine, SessionLocal
from common.logging_config import setup_logger
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from models import Booking
import numpy as np
import threading
import json
from common.config import Config

logger = setup_logger("google_sheets_to_db")

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
    'дополнительный телефон': 'additional_phone',  # Новый столбец
    'Рейсы': 'flights'
  }

  existing_columns = [col for col in column_mapping.keys() if col in df.columns]
  df = df.rename(
    columns={k: v for k, v in column_mapping.items() if k in existing_columns})

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


def process_google_sheets_to_db(google_sheet_key: str, credentials_json: dict):
  """Основная функция синхронизации данных между Google Sheets и БД"""
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

      creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json,
                                                               scope)
      client = gspread.authorize(creds)

      # Открываем таблицу
      spreadsheet = client.open_by_key(google_sheet_key)
      updates = []
      id_clear_updates = []

      # Обрабатываем каждый лист
      for sheet in spreadsheet.worksheets():
        sheet_name = sheet.title
        logger.info(f"Обработка листа: {sheet_name}")

        # Получаем все данные листа
        try:
          all_values = sheet.get_all_values()
          if len(all_values) < 1:
            continue

          headers = all_values[0]
          df = pd.DataFrame(all_values[1:], columns=headers)
        except Exception as e:
          logger.error(f"Ошибка при чтении листа {sheet_name}: {str(e)}")
          continue

        # Очищаем и преобразуем данные
        df = clean_data(df)
        df['sheet_name'] = sheet_name

        # Определяем позицию столбца ID (последний столбец)
        if 'ID' not in headers:
          sheet.add_cols(1)
          id_col_idx = len(headers) + 1
          sheet.update_cell(1, id_col_idx, 'ID')
          headers.append('ID')
          logger.info(f"Добавлен столбец ID в лист {sheet_name}")
        else:
          id_col_idx = headers.index('ID') + 1

        id_col_letter = gspread.utils.rowcol_to_a1(1, id_col_idx)[0]

        # Синхронизируем данные с БД
        with SessionLocal() as session:
          existing_records = session.execute(
              select(Booking).where(Booking.sheet_name == sheet_name)
          ).scalars().all()

          existing_by_id = {r.id: r for r in existing_records}
          existing_by_key = {(r.sheet_name, r.guest, r.booking_date): r
                             for r in existing_records
                             if r.guest and r.booking_date}

          records_to_keep = set()

          for idx, row in df.iterrows():
            row_num = idx + 2
            try:
              row_id = row.get('id')
              is_empty = is_row_empty(row, ['id', 'sheet_name'])

              if is_empty and not row_id:
                continue

              if is_empty and row_id:
                if row_id in existing_by_id:
                  session.delete(existing_by_id[row_id])
                  logger.info(f"Удалена запись с ID: {row_id} (пустая строка)")
                  # Формируем корректный запрос на очистку ID
                  id_clear_updates.append({
                    'range': f"{sheet_name}!{id_col_letter}{row_num}",
                    'values': [[]]  # Пустой массив для очистки ячейки
                  })
                continue

              if pd.isna(row.get('guest')) or pd.isna(row.get('booking_date')):
                continue

              if not row_id:
                record_key = (sheet_name, row['guest'], row['booking_date'])

                if record_key in existing_by_key:
                  db_record = existing_by_key[record_key]
                  if has_changes(db_record, row):
                    update_record(db_record, row)
                    logger.info(f"Обновлена запись с ID: {db_record.id}")

                  # Формируем корректный запрос на обновление ID
                  updates.append({
                    'range': f"{sheet_name}!{id_col_letter}{row_num}",
                    'values': [[str(db_record.id)]]
                  })
                  records_to_keep.add(db_record.id)
                else:
                  new_record = create_new_record(row)
                  session.add(new_record)
                  session.flush()

                  updates.append({
                    'range': f"{sheet_name}!{id_col_letter}{row_num}",
                    'values': [[str(new_record.id)]]
                  })
                  records_to_keep.add(new_record.id)
                  logger.info(f"Добавлена новая запись с ID: {new_record.id}")

              elif row_id:
                if row_id in existing_by_id:
                  db_record = existing_by_id[row_id]
                  if has_changes(db_record, row):
                    update_record(db_record, row)
                    logger.info(f"Обновлена запись с ID: {row_id}")
                  records_to_keep.add(row_id)
                else:
                  new_record = create_new_record(row)
                  new_record.id = row_id
                  session.add(new_record)
                  session.flush()
                  records_to_keep.add(row_id)
                  logger.info(
                    f"Добавлена новая запись с существующим ID: {row_id}")

            except Exception as e:
              logger.error(f"Ошибка при обработке строки {row_num}: {str(e)}")
              continue

          for record in existing_records:
            if record.id not in records_to_keep:
              session.delete(record)
              logger.info(
                f"Удалена запись с ID: {record.id} (отсутствует в таблице)")

          session.commit()

      # Применяем все обновления к Google таблице
      if updates or id_clear_updates:
        try:
          # Объединяем все обновления
          all_updates = updates + id_clear_updates

          # Формируем корректный payload для batch_update
          requests = []
          for update in all_updates:
            requests.append({
              'updateCells': {
                'range': {
                  'sheetId': spreadsheet.worksheet(
                      update['range'].split('!')[0]).id,
                  'startRowIndex': int(update['range'].split('!')[1][1:]) - 1,
                  'endRowIndex': int(update['range'].split('!')[1][1:]),
                  'startColumnIndex': gspread.utils.a1_to_rowcol(
                    update['range'].split('!')[1][0] + '1')[1] - 1,
                  'endColumnIndex': gspread.utils.a1_to_rowcol(
                    update['range'].split('!')[1][0] + '1')[1]
                },
                'rows': [{
                  'values': [{
                    'userEnteredValue': {
                      'stringValue': str(value[0]) if value else None
                    }
                  } for value in update['values']]
                }],
                'fields': 'userEnteredValue'
              }
            })

          # Отправляем обновления порциями по 10 запросов
          batch_size = 10
          for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            spreadsheet.batch_update({'requests': batch})

        except Exception as e:
          logger.error(f"Ошибка при обновлении Google таблицы: {str(e)}",
                       exc_info=True)
          return {"status": "error",
                  "message": f"Ошибка при обновлении таблицы: {str(e)}"}

      logger.info("Синхронизация данных завершена")
      return {"status": "success", "message": "Синхронизация успешно завершена"}

    except Exception as e:
      logger.error(f"Ошибка при обработке Google таблицы: {str(e)}",
                   exc_info=True)
      return {"status": "error",
              "message": f"Ошибка при синхронизации: {str(e)}"}

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
    'comments', 'phone', 'additional_phone', 'flights'  # Добавлен новый столбец
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
    'comments', 'phone', 'additional_phone', 'flights'  # Добавлен новый столбец
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
      additional_phone=row_data.get('additional_phone'),  # Новое поле
      flights=row_data.get('flights')
  )


if __name__ == '__main__':
  process_google_sheets_to_db(
      google_sheet_key=Config.SAMPLE_SPREADSHEET_ID,
      credentials_json=Config.SERVICE_ACCOUNT_FILE
  )