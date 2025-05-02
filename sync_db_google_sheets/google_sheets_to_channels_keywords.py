import json
import threading
from datetime import datetime

import gspread
import numpy as np
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy import select

from common.config import Config
from common.database import SessionLocal
from common.logging_config import setup_logger
from models import ChannelKeyword  # Модель для хранения каналов и ключевых слов

logger = setup_logger("google_sheets_to_channels_keywords")

# Глобальная блокировка для синхронизации
sync_lock = threading.Lock()


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
  """Очищает и преобразует данные DataFrame"""
  column_mapping = {
    'Каналы и группы': 'channels',
    'Ключевые слова': 'keywords',
    'Название канала': 'channel_names'  # Добавлено новое поле
  }

  # Переименовываем колонки
  df = df.rename(
      columns={k: v for k, v in column_mapping.items() if k in df.columns})

  # Обрабатываем колонку с каналами
  if 'channels' in df.columns:
    df['channels'] = df['channels'].apply(
        lambda x: [item.strip() for item in str(x).split(',')] if pd.notna(
            x) else []
    )

  # Обрабатываем колонку с ключевыми словами
  if 'keywords' in df.columns:
    df['keywords'] = df['keywords'].apply(
        lambda x: [item.strip().lower() for item in
                   str(x).split(',')] if pd.notna(x) else []
    )

  # Обрабатываем колонку с названиями каналов
  if 'channel_names' in df.columns:
    df['channel_names'] = df['channel_names'].apply(
        lambda x: str(x).strip() if pd.notna(x) else None
    )

  return df


def process_channels_keywords_sheet(google_sheet_key: str = None,
    credentials_json: dict = None):
  """Основная функция синхронизации данных каналов и ключевых слов

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
      sheet_name = "Поиск в чатах"  # Имя листа с каналами и ключевыми словами
      if sheet_name:
        sheet = spreadsheet.worksheet(sheet_name)
      else:
        sheet = spreadsheet.get_worksheet(0)  # fallback на первый лист
        sheet_name = sheet.title
      logger.info(f"Обработка листа мониторинга: {sheet_name}")

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
        # Получаем все существующие записи
        existing_records = session.execute(
            select(ChannelKeyword)
        ).scalars().all()

        # Словарь для быстрого поиска по каналу
        existing_records_map = {
          record.channel: record for record in existing_records
        }

        # Обрабатываем каждую строку таблицы
        for idx, row in df.iterrows():
          try:
            channels = row.get('channels', [])
            keywords = row.get('keywords', [])
            channel_names = row.get('channel_names')  # Получаем название канала

            for channel in channels:
              if channel in existing_records_map:
                # Обновляем существующую запись
                db_record = existing_records_map[channel]
                if has_channel_changes(db_record, keywords, channel_names):
                  update_channel_keywords(db_record, keywords, channel_names)
                  logger.info(f"Обновлены данные для канала: {channel}")
              else:
                # Создаем новую запись
                new_record = create_channel_keyword(channel, keywords,
                                                    channel_names)
                session.add(new_record)
                logger.info(f"Добавлен новый канал: {channel}")

          except Exception as e:
            logger.error(f"Ошибка при обработке строки {idx + 2}: {str(e)}")
            continue

        # Удаляем записи, которых нет в таблице
        current_channels = set()
        for _, row in df.iterrows():
          current_channels.update(row.get('channels', []))

        for record in existing_records:
          if record.channel not in current_channels:
            session.delete(record)
            logger.info(f"Удален канал: {record.channel}")

        session.commit()

      logger.info("Синхронизация каналов и ключевых слов завершена")
      return {"status": "success", "message": "Синхронизация успешно завершена"}

    except Exception as e:
      logger.error(f"Ошибка при обработке Google таблицы: {str(e)}",
                   exc_info=True)
      return {"status": "error",
              "message": f"Ошибка при синхронизации: {str(e)}"}


def has_channel_changes(db_record, new_keywords, new_channel_names):
  """Проверяет, есть ли различия между записью в БД и данными из таблицы"""
  current_keywords = set(
      db_record.keywords.split(',')) if db_record.keywords else set()
  new_keywords_set = set(new_keywords)

  # Проверяем изменения в ключевых словах и названии канала
  keyword_changes = current_keywords != new_keywords_set
  name_changes = (db_record.channel_names or None) != (new_channel_names or None)

  return keyword_changes or name_changes


def update_channel_keywords(db_record, keywords, channel_names):
  """Обновляет существующую запись в БД"""
  db_record.keywords = ','.join(keywords)
  db_record.channel_names = channel_names
  db_record.last_updated = datetime.now()


def create_channel_keyword(channel, keywords, channel_names):
  """Создает новую запись для БД"""
  return ChannelKeyword(
      channel=channel,
      keywords=','.join(keywords),
      channel_names=channel_names,
      last_updated=datetime.now()
  )


if __name__ == '__main__':
  process_channels_keywords_sheet()