# main_tg_bot/command/view_dates.py

from datetime import date, timedelta
import pandas as pd
import os
from telegram import Update
from typing import List, Tuple
from common.logging_config import setup_logger
from common.config import Config

logger = setup_logger("view_dates")

# Новая папка с данными бронирований
BOOKING_DATA_DIR = Config.BOOKING_DATA_DIR


def get_all_booking_files() -> list:
    """Возвращает список всех .csv файлов в папке booking/"""
    if not os.path.exists(BOOKING_DATA_DIR):
        return []
    files = [
        f for f in os.listdir(BOOKING_DATA_DIR)
        if f.endswith('.csv') and os.path.isfile(os.path.join(BOOKING_DATA_DIR, f))
    ]
    return sorted(files)


def format_file_name(file_name: str) -> str:
    """Форматирование имени файла для отображения в Telegram"""
    name = file_name.replace('.csv', '').replace('_', ' ').title()
    return name


def get_file_path(file_name: str) -> str:
    """Получить полный путь к файлу"""
    return os.path.join(BOOKING_DATA_DIR, file_name)


def load_bookings_from_csv(file_name: str):
    """Загрузка данных из CSV файла"""
    try:
        file_path = get_file_path(file_name)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        df = pd.read_csv(file_path, encoding='utf-8')
        df = df.fillna('')

        required_cols = {'Заезд', 'Выезд'}
        if not required_cols.issubset(df.columns):
            logger.error(f"Missing required columns in {file_name}. Found: {df.columns.tolist()}")
            return None

        df['Заезд'] = pd.to_datetime(df['Заезд'], format='%d.%m.%Y', errors='coerce')
        df['Выезд'] = pd.to_datetime(df['Выезд'], format='%d.%m.%Y', errors='coerce')
        df = df.dropna(subset=['Заезд', 'Выезд'])

        return df
    except Exception as e:
        logger.error(f"Error loading CSV file {file_name}: {e}", exc_info=True)
        return None


async def view_dates_handler(update: Update, context):
    """Вывод всех свободных диапазонов дат в разрезе CSV файлов"""
    csv_files = get_all_booking_files()

    if not csv_files:
        await update.message.reply_text("📭 Нет доступных файлов бронирований в папке `booking/`")
        return

    for file_name in csv_files:
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
            check_in = row['Заезд'].date()
            check_out = row['Выезд'].date()
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


def find_free_periods(
    booked_periods: List[Tuple[date, date]],
    start_date: date = None,
    end_date: date = None
) -> List[Tuple[date, date]]:
    """
    Находит свободные периоды между занятыми датами.

    Args:
        booked_periods: Список кортежей (check_in, check_out)
        start_date: Дата начала поиска (по умолчанию сегодня)
        end_date: Дата окончания поиска (по умолчанию +1 год от сегодня)

    Returns:
        Список кортежей с начальной и конечной датами свободных периодов
    """
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = date.today() + timedelta(days=365)

    if not booked_periods:
        return [(start_date, end_date)]

    # Сортируем по дате заезда
    sorted_periods = sorted(booked_periods, key=lambda x: x[0])

    free_periods = []
    previous_end = start_date

    for current_start, current_end in sorted_periods:
        # Пропускаем периоды, которые заканчиваются до начала диапазона
        if current_end < start_date:
            if current_end > previous_end:
                previous_end = current_end
            continue

        # Обрезаем начало, если оно раньше start_date
        actual_start = max(current_start, start_date)

        # Если есть промежуток между previous_end и actual_start
        if previous_end < actual_start:
            free_end = actual_start - timedelta(days=1)
            if free_end >= previous_end:
                free_periods.append((previous_end, free_end))

        # Обновляем previous_end
        if current_end > previous_end:
            previous_end = current_end

        # Если вышли за пределы end_date — завершаем
        if previous_end >= end_date:
            break

    # Проверяем финальный промежуток
    if previous_end < end_date:
        free_periods.append((previous_end, end_date))

    # Фильтруем корректные периоды (начало <= конец)
    free_periods = [(s, e) for s, e in free_periods if s <= e]

    return free_periods