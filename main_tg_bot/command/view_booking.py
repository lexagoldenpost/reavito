from datetime import date
import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from common.logging_config import setup_logger
from common.config import Config  # Импортируем ваш конфиг
import os

logger = setup_logger("view_booking")

# Используем конфиг для получения списка CSV файлов
CSV_FILES = Config.BOOKING_FILE_CSV_ID

# Добавляем префиксы для callback-данных
VB_CALLBACK_PREFIX = "vb_"  # vb = view_booking
VB_SHEET_SELECT = f"{VB_CALLBACK_PREFIX}sheet"

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


async def view_booking_handler(update, context):
    """Обработчик для просмотра бронирований"""
    try:
        logger.info(f"view_booking_handler called with update type: {type(update)}")

        if update.callback_query:
            logger.info(f"Callback query data: {update.callback_query.data}")
            # Проверяем, что callback относится к этому модулю
            if update.callback_query.data.startswith(VB_CALLBACK_PREFIX):
                logger.info("Callback belongs to view_booking module, processing...")
                return await handle_callback(update, context)
            else:
                # Пропускаем callback, если он не для этого модуля
                logger.info(f"Callback not for view_booking, skipping: {update.callback_query.data}")
                return
        elif update.message:
            logger.info(f"Message received: {update.message.text}")
            return await handle_message(update, context)
        else:
            logger.error("Unknown update type in view_booking_handler")

    except Exception as e:
        logger.error(f"Error in view_booking_handler: {e}", exc_info=True)
        error_message = "Произошла ошибка при обработке запроса"
        await send_reply(update, error_message)


async def handle_message(update, context):
    """Обработка текстового сообщения"""
    try:
        logger.info("handle_message called")
        if 'step' not in context.user_data or context.user_data['step'] == 1:
            await show_file_selection(update, context)
            context.user_data['step'] = 2
        elif context.user_data['step'] == 2:
            selected_file = update.message.text.strip()
            await show_bookings(update, context, selected_file)
            del context.user_data['step']
    except Exception as e:
        logger.error(f"Error in handle_message: {e}", exc_info=True)


async def handle_callback(update, context):
    """Обработка нажатия на кнопку"""
    try:
        query = update.callback_query
        logger.info(f"handle_callback called with data: {query.data}")
        await query.answer()

        logger.info(f"Received callback: {query.data}")

        if query.data.startswith(VB_SHEET_SELECT):
            # Извлекаем имя файла из callback данных
            selected_file = query.data.replace(f"{VB_SHEET_SELECT}_", "")
            logger.info(f"Selected file: {selected_file}")
            await show_bookings(update, context, selected_file)

        try:
            await query.message.delete()
            logger.info("Previous message deleted")
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")

        if 'step' in context.user_data:
            del context.user_data['step']

    except Exception as e:
        logger.error(f"Error in handle_callback: {e}", exc_info=True)


async def show_file_selection(update, context):
    """Показать пользователю список доступных CSV файлов с кнопками"""
    try:
        if not CSV_FILES:
            await send_reply(update, "Нет доступных файлов для выбора")
            return

        logger.info(f"Available CSV files: {CSV_FILES}")

        keyboard = []
        for file_name in CSV_FILES:
            # Форматируем имя файла для отображения
            display_name = format_file_name(file_name)
            callback_data = f"{VB_SHEET_SELECT}_{file_name}"
            logger.info(f"Creating button: {display_name} -> {callback_data}")
            keyboard.append([InlineKeyboardButton(display_name, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await send_reply(update, "Выберите файл для просмотра бронирований:", reply_markup)

    except Exception as e:
        logger.error(f"Error in show_file_selection: {e}", exc_info=True)
        await send_reply(update, "Ошибка при получении списка файлов")


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
        logger.info(f"First few rows: {df.head(2).to_dict('records')}")

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


async def show_bookings(update, context, file_name):
    """Показать бронирования для выбранного файла"""
    try:
        logger.info(f"show_bookings called with file: {file_name}")

        if file_name not in CSV_FILES:
            error_msg = f"Файл {file_name} не найден в списке доступных. Доступные: {CSV_FILES}"
            logger.error(error_msg)
            await send_reply(update, error_msg)
            return

        df = load_bookings_from_csv(file_name)
        if df is None:
            await send_reply(update, f"❌ Не удалось загрузить данные из файла {file_name}")
            return

        if df.empty:
            await send_reply(update, f"📭 Файл {file_name} не содержит данных")
            return

        # Фильтрация активных бронирований (выезд >= сегодня)
        today = date.today()
        logger.info(f"Filtering bookings with check-out >= {today}")

        active_bookings = df[df['Выезд'].dt.date >= today].copy()
        logger.info(f"Found {len(active_bookings)} active bookings")

        # Сортировка по дате заезда
        active_bookings = active_bookings.sort_values('Заезд')

        if active_bookings.empty:
            await send_reply(update, f"📭 Нет активных бронирований в файле {format_file_name(file_name)}")
            return

        messages = prepare_booking_messages(file_name, active_bookings)

        for msg in messages:
            await send_reply(update, msg, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in show_bookings: {e}", exc_info=True)
        await send_reply(update, "❌ Ошибка при получении данных о бронированиях")


def format_date(dt):
    """Форматирование даты в dd.mm.yyyy"""
    if hasattr(dt, 'strftime'):
        return dt.strftime("%d.%m.%Y")
    return str(dt)


def prepare_booking_messages(file_name, bookings_df):
    """Подготовка сообщений с информацией о бронированиях"""
    messages = []
    # Используем форматированное имя файла для отображения
    display_file_name = format_file_name(file_name)
    current_message = f"<b>📅 Бронирования из файла {display_file_name}:</b>\n\n"

    # Преобразуем DataFrame в список словарей для удобства обработки
    bookings = bookings_df.to_dict('records')
    logger.info(f"Preparing messages for {len(bookings)} bookings")

    for i in range(len(bookings)):
        booking = bookings[i]

        # Извлекаем данные из CSV структуры
        guest = booking.get('Гость', 'Не указан')
        check_in = booking.get('Заезд')
        check_out = booking.get('Выезд')

        # Вычисляем количество ночей
        nights = (check_out - check_in).days if check_in and check_out else 0

        booking_info = (
            f"<b>🏠 Бронь #{i + 1}</b>\n"
            f"<b>{guest}</b>\n"
            f"📅 {format_date(check_in)} - {format_date(check_out)}\n"
            f"🌙 Ночей: {nights}\n"
            f"💵 Сумма: {booking.get('СуммаБатты', 'Не указана')} батт\n\n"
        )

        if len(current_message + booking_info) > 4000:
            messages.append(current_message)
            current_message = booking_info
        else:
            current_message += booking_info

        # Добавляем информацию о свободных периодах между бронированиями
        if i < len(bookings) - 1:
            next_booking = bookings[i + 1]
            next_check_in = next_booking.get('Заезд')

            if check_out and next_check_in and check_out != next_check_in:
                free_nights = (next_check_in - check_out).days
                if free_nights > 0:
                    free_period = (
                        f"🆓 Свободно:\n"
                        f"📅 С {format_date(check_out)} - По {format_date(next_check_in)}\n"
                        f"🌙 {free_nights} ночей\n\n"
                    )

                    if len(current_message + free_period) > 4000:
                        messages.append(current_message)
                        current_message = free_period
                    else:
                        current_message += free_period

    messages.append(current_message)
    logger.info(f"Prepared {len(messages)} message(s)")
    return messages


async def send_reply(update, text, reply_markup=None, parse_mode=None):
    """Универсальная функция отправки сообщения"""
    try:
        if update.callback_query:
            return await update.callback_query.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif update.message:
            return await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    except Exception as e:
        logger.error(f"Error in send_reply: {e}", exc_info=True)