# Синхронизация таблицы заданий
import pandas as pd
from sqlalchemy import select, delete
from common.database import engine, SessionLocal
from common.logging_config import setup_logger
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from models import Notification  # Новая модель для уведомлений
import numpy as np
import threading
import json
from common.config import Config
from datetime import datetime

logger = setup_logger("google_sheets_to_notifications")

# Глобальная блокировка для синхронизации
sync_lock = threading.Lock()


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
  """Очищает и преобразует данные DataFrame"""
  column_mapping = {
    'Оповещение': 'notification_type',
    'Время старта по МСК': 'start_time',
    'Триггер по объекту': 'trigger_object',
    'Если новое бронирование после триггера в днях отправляем или нет': 'send_if_new',
    'Триггер по столбцу': 'trigger_column',
    'Тригер срок в днях (минус срок до, без срок после)': 'trigger_days',
    'Сообщение': 'message'
  }

  existing_columns = [col for col in column_mapping.keys() if col in df.columns]
  df = df.rename(
      columns={k: v for k, v in column_mapping.items() if
               k in existing_columns})

  # Преобразуем время
  if 'start_time' in df.columns:
    df['start_time'] = pd.to_datetime(df['start_time'],
                                      format='%H:%M:%S').dt.time

  # Преобразуем числовые поля
  if 'trigger_days' in df.columns:
    df['trigger_days'] = pd.to_numeric(df['trigger_days'], errors='coerce')

  # Заменяем NaN/NaT на None
  df = df.replace([np.nan, pd.NaT], None)

  return df


def process_notifications_sheet(google_sheet_key: str = None,
    credentials_json: dict = None):
  """Основная функция синхронизации данных уведомлений

  Args:
      google_sheet_key (str, optional): Ключ Google таблицы. По умолчанию берется из конфига.
      credentials_json (dict, optional): Данные авторизации. По умолчанию берется из конфига.
  """
  # Установка значений по умолчанию из конфига
  if google_sheet_key is None:
    google_sheet_key = Config.NOTIFICATIONS_SPREADSHEET_ID
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

      creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json,
                                                               scope)
      client = gspread.authorize(creds)

      # Открываем таблицу (работаем только с первым листом)
      spreadsheet = client.open_by_key(google_sheet_key)
      sheet = spreadsheet.get_worksheet(0)  # Получаем первый лист
      sheet_name = sheet.title
      logger.info(f"Обработка листа уведомлений: {sheet_name}")

      # Получаем все данные листа
      try:
        all_values = sheet.get_all_values()
        if len(all_values) < 1:
          return {"status": "error", "message": "Таблица пуста"}

        headers = all_values[0]
        df = pd.DataFrame(all_values[1:], columns=headers)
      except Exception as e:
        logger.error(f"Ошибка при чтении листа {sheet_name}: {str(e)}")
        return {"status": "error",
                "message": f"Ошибка чтения таблицы: {str(e)}"}

      # Очищаем и преобразуем данные
      df = clean_data(df)

      # Синхронизируем данные с БД
      with SessionLocal() as session:
        # Получаем все существующие уведомления
        existing_notifications = session.execute(
            select(Notification)
        ).scalars().all()

        # Словарь для быстрого поиска по ключевым полям
        existing_notifs_map = {
          (n.notification_type, n.trigger_object, n.trigger_column): n
          for n in existing_notifications
        }

        # Обрабатываем каждую строку таблицы
        for idx, row in df.iterrows():
          try:
            # Ключ для поиска существующего уведомления
            notif_key = (
              row['notification_type'],
              row['trigger_object'],
              row['trigger_column']
            )

            if notif_key in existing_notifs_map:
              # Обновляем существующее уведомление
              db_notif = existing_notifs_map[notif_key]
              if has_notification_changes(db_notif, row):
                update_notification(db_notif, row)
                logger.info(f"Обновлено уведомление: {notif_key}")
            else:
              # Создаем новое уведомление
              new_notif = create_notification(row)
              session.add(new_notif)
              logger.info(f"Добавлено новое уведомление: {notif_key}")

          except Exception as e:
            logger.error(f"Ошибка при обработке строки {idx + 2}: {str(e)}")
            continue

        # Удаляем уведомления, которых нет в таблице
        current_notifs = {
          (row['notification_type'], row['trigger_object'],
           row['trigger_column'])
          for _, row in df.iterrows()
        }

        for notif in existing_notifications:
          notif_key = (
            notif.notification_type, notif.trigger_object, notif.trigger_column)
          if notif_key not in current_notifs:
            session.delete(notif)
            logger.info(f"Удалено уведомление: {notif_key}")

        session.commit()

      logger.info("Синхронизация уведомлений завершена")
      return {"status": "success", "message": "Синхронизация успешно завершена"}

    except Exception as e:
      logger.error(f"Ошибка при обработке Google таблицы: {str(e)}",
                   exc_info=True)
      return {"status": "error",
              "message": f"Ошибка при синхронизации: {str(e)}"}


def has_notification_changes(db_notif, row_data):
  """Проверяет, есть ли различия между уведомлением в БД и данными из таблицы"""
  for column in [
    'notification_type', 'start_time', 'trigger_object',
    'send_if_new', 'trigger_column', 'trigger_days', 'message'
  ]:
    if column in row_data:
      db_value = getattr(db_notif, column)
      sheet_value = row_data[column]

      if db_value != sheet_value:
        if pd.isna(db_value) and pd.isna(sheet_value):
          continue
        return True
  return False


def update_notification(db_notif, row_data):
  """Обновляет существующее уведомление в БД"""
  for column in [
    'notification_type', 'start_time', 'trigger_object',
    'send_if_new', 'trigger_column', 'trigger_days', 'message'
  ]:
    if column in row_data:
      setattr(db_notif, column, row_data[column])


def create_notification(row_data):
  """Создает новое уведомление для БД"""
  return Notification(
      notification_type=row_data.get('notification_type'),
      start_time=row_data.get('start_time'),
      trigger_object=row_data.get('trigger_object'),
      send_if_new=row_data.get('send_if_new'),
      trigger_column=row_data.get('trigger_column'),
      trigger_days=row_data.get('trigger_days'),
      message=row_data.get('message'),
      last_updated=datetime.now()
  )


if __name__ == '__main__':
  process_notifications_sheet()