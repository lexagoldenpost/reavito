# main_tg_bot/command/view_dates.py

from datetime import date, timedelta
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from telegram import Update

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT, get_all_booking_files

logger = setup_logger("view_dates")

# Путь к папке booking/ относительно корня проекта
BOOKING_DATA_DIR = PROJECT_ROOT / Config.BOOKING_DATA_DIR


def format_file_name(file_name: str) -> str:
    """Форматирование имени файла для отображения в Telegram"""
    name = file_name.replace('.csv', '').replace('_', ' ').title()
    return name


def get_file_path(file_name: str) -> str:
    """Получить полный путь к файлу"""
    return str(BOOKING_DATA_DIR / file_name)


def load_bookings_from_csv(file_name: str):
    """Загрузка данных из CSV файла"""
    try:
        file_path = get_file_path(file_name)
        if not Path(file_path).exists():
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
        await update.message.reply_text("📭 Нет доступных файлов бронирований в папке `booking_files/`")
        return

    for file_name in csv_files:
        df = load_bookings_from_csv(file_name)

        if df is None:
            await update.message.reply_text(f"❌ Не удалось загрузить данные из файла {file_name}")
            continue

        if df.empty:
            await update.message.reply_text(f"📭 Файл {file_name} не содержит данных")
            continue

        # Проверяем, является ли файл booking_other
        is_booking_other = "booking_other" in file_name.lower()

        # Если это booking_other, пропускаем показ свободных дат
        if is_booking_other:
          continue  # просто пропускаем этот файл

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
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = date.today() + timedelta(days=365)

    if not booked_periods:
        return [(start_date, end_date)]

    sorted_periods = sorted(booked_periods, key=lambda x: x[0])
    free_periods = []
    current = start_date

    for check_in, check_out in sorted_periods:
        if check_out <= current:
            continue
        if current < check_in:
            period_end = min(check_in, end_date)
            if current < period_end:
                free_periods.append((current, period_end))
        if check_out > current:
            current = check_out
        if current >= end_date:
            break

    if current < end_date:
        free_periods.append((current, end_date))

    return free_periods