# view_dates.py
from datetime import date, timedelta
import pandas as pd
import os
from telegram import Update
from typing import List, Tuple
from common.logging_config import setup_logger
from common.config import Config

logger = setup_logger("view_dates")

# Используем конфиг для получения списка CSV файлов
CSV_FILES = Config.BOOKING_FILE_CSV_ID

# Путь к папке с данными бронирований
BOOKING_DATA_DIR = "booking_data"


def format_file_name(file_name):
    """Форматирование имени файла для отображения в Telegram"""
    # Убираем расширение .csv
    name_without_ext = file_name.replace('.csv', '')
    # Заменяем нижние подчеркивания на пробелы
    name_with_spaces = name_without_ext.replace('_', ' ')
    # Преобразуем в camel case (каждое слово с заглавной буквы)
    formatted_name = name_with_spaces.title()
    return formatted_name


def get_file_path(file_name):
    """Получить полный путь к файлу с учетом папки booking_data"""
    return os.path.join(BOOKING_DATA_DIR, file_name)


def load_bookings_from_csv(file_name):
    """Загрузка данных из CSV файла"""
    try:
        file_path = get_file_path(file_name)
        logger.info(f"Attempting to load CSV file: {file_path}")

        # Проверяем существование файла
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        logger.info(f"File exists, reading CSV...")
        df = pd.read_csv(file_path, encoding='utf-8')
        logger.info(f"Successfully loaded CSV with {len(df)} rows")
        logger.info(f"Columns: {df.columns.tolist()}")

        # Преобразование дат из формата dd.mm.yyyy
        df['Заезд'] = pd.to_datetime(df['Заезд'], format='%d.%m.%Y', errors='coerce')
        df['Выезд'] = pd.to_datetime(df['Выезд'], format='%d.%m.%Y', errors='coerce')

        # Фильтрация записей с валидными датами
        initial_count = len(df)
        df = df.dropna(subset=['Заезд', 'Выезд'])
        filtered_count = len(df)

        logger.info(f"After date filtering: {filtered_count} rows (was {initial_count})")

        return df
    except Exception as e:
        logger.error(f"Error loading CSV file {file_name}: {e}", exc_info=True)
        return None


async def view_dates_handler(update: Update, context):
    """Вывод всех свободных диапазонов дат в разрезе CSV файлов"""
    if not CSV_FILES:
        await update.message.reply_text("Нет доступных файлов для просмотра.")
        return

    for file_name in CSV_FILES:
        # Загружаем данные из CSV файла
        df = load_bookings_from_csv(file_name)

        if df is None:
            await update.message.reply_text(f"❌ Не удалось загрузить данные из файла {file_name}")
            continue

        if df.empty:
            await update.message.reply_text(f"📭 Файл {file_name} не содержит данных")
            continue

        # Формируем список занятых периодов
        booked_periods = []
        for _, row in df.iterrows():
            check_in = row['Заезд'].date() if hasattr(row['Заезд'], 'date') else row['Заезд']
            check_out = row['Выезд'].date() if hasattr(row['Выезд'], 'date') else row['Выезд']

            # Проверяем, что даты валидны
            if isinstance(check_in, date) and isinstance(check_out, date):
                booked_periods.append((check_in, check_out))

        # Находим свободные периоды
        free_periods = find_free_periods(booked_periods)

        # Формируем сообщение
        display_name = format_file_name(file_name)
        message = f"📅 <b>Свободные даты для {display_name}</b>\n\n"

        if not free_periods:
            message += "❌ Нет свободных периодов"
        else:
            message += "🆓 Свободно:\n"
            for start, end in free_periods:
                nights = (end - start).days
                message += (
                    f"📅 С {start.strftime('%d.%m.%Y')} - По {end.strftime('%d.%m.%Y')}\n"
                    f"🌙 {nights} ночей\n\n"
                )

        await update.message.reply_text(message, parse_mode='HTML')


def find_free_periods(booked_periods: List[Tuple[date, date]],
                      start_date: date = date.today(),
                      end_date: date = date.today() + timedelta(days=365)) -> List[Tuple[date, date]]:
    """
  Находит свободные периоды между занятыми датами.

  Args:
      booked_periods: Список кортежей (check_in, check_out)
      start_date: Дата начала поиска (по умолчанию сегодня)
      end_date: Дата окончания поиска (по умолчанию +1 год от сегодня)

  Returns:
      Список кортежей с начальной и конечной датами свободных периодов
  """
    if not booked_periods:
        return [(start_date, end_date)]

    # Сортируем периоды по дате заезда
    sorted_periods = sorted(booked_periods, key=lambda x: x[0])

    free_periods = []
    previous_end = start_date

    for period in sorted_periods:
        current_start, current_end = period

        # Если между предыдущим и текущим периодом есть промежуток
        if previous_end < current_start:
            free_periods.append((previous_end, current_start - timedelta(days=1)))

        # Обновляем previous_end до максимальной даты
        if current_end > previous_end:
            previous_end = current_end

    # Проверяем период после последнего бронирования
    if previous_end < end_date:
        free_periods.append((previous_end, end_date))

    return free_periods