# chat_sync.py
import json
import threading
from datetime import datetime

import gspread
import numpy as np
import pandas as pd
from common.database import Base, engine, SessionLocal
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy import select

from common.config import Config
from common.logging_config import setup_logger
from old.sync_db_google_sheets.models import Chat

logger = setup_logger("google_sheets_to_chats")

# Глобальная блокировка для синхронизации
sync_lock = threading.Lock()

def clean_chat_data(df: pd.DataFrame) -> pd.DataFrame:
    """Очищает и преобразует данные DataFrame для чатов"""
    column_mapping = {
        'Наименование чата': 'chat_name',
        'Срок в днях меньше которого не отправляем': 'send_frequency',
        'Картинки принимает (Да/Нет)': 'accepts_images',
        'Объект': 'chat_object',
        'Название канала': 'channel_name'  # Добавлен новый столбец
    }

    # Переименовываем колонки
    existing_columns = [col for col in column_mapping.keys() if col in df.columns]
    df = df.rename(
        columns={k: v for k, v in column_mapping.items() if k in existing_columns})

    # Преобразуем числовые поля
    if 'send_frequency' in df.columns:
        df['send_frequency'] = pd.to_numeric(df['send_frequency'], errors='coerce')

    # Преобразуем Да/Нет в Boolean
    if 'accepts_images' in df.columns:
        df['accepts_images'] = df['accepts_images'].apply(
            lambda x: True if str(x).lower() in ['да', 'yes', 'true', '1'] else False)

    # Заменяем NaN/NaT на None
    df = df.replace([np.nan, pd.NaT], None)

    return df

def process_chats_sheet(google_sheet_key: str = None,
                       credentials_json: dict = None):
    """Основная функция синхронизации данных чатов"""
    # Установка значений по умолчанию из конфига
    if google_sheet_key is None:
        google_sheet_key = Config.BOOKING_TASK_SPREADSHEET_ID
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

            # Открываем таблицу
            spreadsheet = client.open_by_key(google_sheet_key)

            sheet_name = "Отправка бронирований"
            if sheet_name:
                sheet = spreadsheet.worksheet(sheet_name)
            else:
                sheet = spreadsheet.get_worksheet(0)  # fallback на первый лист
                sheet_name = sheet.title

            logger.info(f"Обработка листа чатов: {sheet_name}")

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
            df = clean_chat_data(df)

            # Синхронизируем данные с БД
            with SessionLocal() as session:
                # Получаем все существующие чаты
                existing_chats = session.execute(
                    select(Chat)
                ).scalars().all()

                # Словарь для быстрого поиска по названию чата
                existing_chats_map = {
                    chat.chat_name: chat for chat in existing_chats
                }

                # Обрабатываем каждую строку таблицы
                for idx, row in df.iterrows():
                    try:
                        chat_name = row['chat_name']
                        if not chat_name or pd.isna(chat_name):
                            continue

                        if chat_name in existing_chats_map:
                            # Обновляем существующий чат
                            db_chat = existing_chats_map[chat_name]
                            if has_chat_changes(db_chat, row):
                                update_chat(db_chat, row)
                                logger.info(f"Обновлен чат: {chat_name}")
                        else:
                            # Создаем новый чат
                            new_chat = create_chat(row)
                            session.add(new_chat)
                            logger.info(f"Добавлен новый чат: {chat_name}")

                    except Exception as e:
                        logger.error(f"Ошибка при обработке строки {idx + 2}: {str(e)}")
                        continue

                # Удаляем чаты, которых нет в таблице
                current_chats = {row['chat_name'] for _, row in df.iterrows()
                               if row['chat_name'] and not pd.isna(row['chat_name'])}

                for chat in existing_chats:
                    if chat.chat_name not in current_chats:
                        session.delete(chat)
                        logger.info(f"Удален чат: {chat.chat_name}")

                session.commit()

            logger.info("Синхронизация чатов завершена")
            return {"status": "success", "message": "Синхронизация успешно завершена"}

        except Exception as e:
            logger.error(f"Ошибка при обработке Google таблицы: {str(e)}",
                        exc_info=True)
            return {"status": "error",
                    "message": f"Ошибка при синхронизации: {str(e)}"}

def has_chat_changes(db_chat, row_data):
    """Проверяет, есть ли различия между чатом в БД и данными из таблицы"""
    for column in ['chat_name', 'send_frequency', 'accepts_images', 'chat_object', 'channel_name']:
        if column in row_data:
            db_value = getattr(db_chat, column)
            sheet_value = row_data[column]

            if db_value != sheet_value:
                if pd.isna(db_value) and pd.isna(sheet_value):
                    continue
                return True
    return False

def update_chat(db_chat, row_data):
    """Обновляет существующий чат в БД"""
    for column in ['chat_name', 'send_frequency', 'accepts_images', 'chat_object', 'channel_name']:
        if column in row_data:
            setattr(db_chat, column, row_data[column])
    db_chat.last_updated = datetime.now()

def create_chat(row_data):
    """Создает новый чат для БД"""
    return Chat(
        chat_name=row_data.get('chat_name'),
        send_frequency=row_data.get('send_frequency'),
        accepts_images=row_data.get('accepts_images'),
        chat_object=row_data.get('chat_object'),
        channel_name=row_data.get('channel_name'),  # Новое поле
        last_updated=datetime.now()
    )

if __name__ == '__main__':
    # Создаем таблицу в БД, если ее нет
    Base.metadata.create_all(bind=engine)
    process_chats_sheet()