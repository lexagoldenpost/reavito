import asyncio
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from telega.send_tg_reklama import TelegramSender  # Импортируем класс для отправки
from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT

logger = setup_logger("halo_send_to_telegram_chats_bookings")

# Конфигурация из переменных окружения
IMAGES_FOLDER = Path(Config.IMAGES_FOLDER) if Config.IMAGES_FOLDER else None
# Определяем путь к папке booking относительно корня проекта
BOOKING_DATA_DIR = PROJECT_ROOT / Config.BOOKING_DATA_DIR / "halo_title.csv"


class CSVBooking:
    """Класс для представление бронирования из CSV файла"""

    def __init__(self, row):
        self.sheet_name = "Halo"  # Название объекта по умолчанию
        self.check_in = self._parse_date(row.get('Заезд', '').strip())
        self.check_out = self._parse_date(row.get('Выезд', '').strip())

    def _parse_date(self, date_str):
        """Парсит дату из строки формата DD.MM.YYYY"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            return None


def read_bookings_from_csv(csv_file_path: str, title: str) -> List[CSVBooking]:
    """Читает бронирования из CSV файла и возвращает список объектов CSVBooking"""
    bookings = []

    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=',')

            for row in reader:
                # Пропускаем пустые строки
                if not any(row.values()):
                    continue

                booking = CSVBooking(row)
                bookings.append(booking)

        logger.info(f"Прочитано {len(bookings)} бронирований из CSV файла")
        return bookings

    except Exception as e:
        logger.error(f"Ошибка чтения CSV файла: {str(e)}")
        return []


def filter_free_bookings(bookings: List[CSVBooking]) -> List[CSVBooking]:
    """
    Фильтрует только свободные бронирования от текущей даты + 3 месяца вперед
    """
    current_date = datetime.now().date()
    future_date = current_date + timedelta(days=90)  # +3 месяца

    free_bookings = []

    for booking in bookings:
        # Проверяем, что это свободный период (только check_out указан)
        if booking.check_in is None and booking.check_out:
            # Проверяем, что дата освобождения в пределах нашего диапазона
            if booking.check_out <= future_date:
                free_bookings.append(booking)
        # Для периодов с обеими датами проверяем, что они свободны и в диапазоне
        elif booking.check_in and booking.check_out:
            # Проверяем, что период начинается не раньше текущей даты
            # и заканчивается не позже чем через 3 месяца
            if (booking.check_in >= current_date and
                    booking.check_out <= future_date):
                free_bookings.append(booking)

    logger.info(f"Отфильтровано {len(free_bookings)} свободных бронирований на ближайшие 3 месяца")
    return free_bookings


async def get_free_periods(bookings: List[CSVBooking]) -> List[Tuple[datetime.date, datetime.date, int]]:
    """
    Возвращает список свободных периодов от текущей даты + 3 месяца вперед
    """
    current_date = datetime.now().date()
    future_date = current_date + timedelta(days=90)  # +3 месяца

    # Фильтруем только свободные бронирования в нужном диапазоне
    free_bookings = filter_free_bookings(bookings)

    if not free_bookings:
        return []

    # Сортируем по дате начала
    sorted_bookings = sorted(
        [b for b in free_bookings if b.check_out is not None],
        key=lambda x: x.check_out
    )

    free_periods = []

    # Обрабатываем периоды с обеими датами
    for booking in sorted_bookings:
        if booking.check_in and booking.check_out:
            # Проверяем, что период в пределах 3 месяцев
            if booking.check_in >= current_date and booking.check_out <= future_date:
                nights = (booking.check_out - booking.check_in).days
                free_periods.append((booking.check_in, booking.check_out, nights))

    # Добавляем периоды "и далее" (только check_out)
    for booking in free_bookings:
        if booking.check_in is None and booking.check_out:
            # Проверяем, что дата в пределах 3 месяцев
            if booking.check_out <= future_date:
                free_periods.append((booking.check_out, None, 999))  # 999 означает "и далее"

    return free_periods


async def format_free_dates_message(bookings: List[CSVBooking]) -> str:
    """
    Форматирует сообщение со свободными датами на 3 месяца вперед
    """
    free_periods = await get_free_periods(bookings)

    if not free_periods:
        return "На ближайшие 3 месяцев нет свободных дат"

    date_ranges = []

    for start, end, nights in free_periods:
        if end is None:  # Период "и далее"
            date_ranges.append(f"с {start.strftime('%d.%m.%y')} и далее")
        else:
            date_ranges.append(f"{start.strftime('%d.%m.%y')}-{end.strftime('%d.%m.%y')} ({nights} ночей)")

    return "\n".join(date_ranges)


async def send_to_specific_chat(
        chat_id: str,
        title: str,
        csv_file_path: str = BOOKING_DATA_DIR,
        images: Optional[List[Path]] = None
) -> bool:
    """Отправляет уведомление в конкретный чат/группу по ID и возвращает результат отправки

    Args:
        chat_id (str): ID чата/группы в Telegram (может начинаться с минуса)
        title (str): Название объекта для поиска в CSV файле
        csv_file_path (str): Путь к CSV файлу с данными бронирований
        images (Optional[List[Path]]): Список путей к изображениям для отправки

    Returns:
        bool: True если сообщение отправлено успешно, False в случае ошибки
    """
    logger.info(f"Запуск отправки в чат {chat_id} для объекта: {title}")

    try:
        # Читаем бронирования из CSV файла
        bookings = read_bookings_from_csv(csv_file_path, title)

        if not bookings:
            logger.info(f"Нет данных о бронированиях для объекта {title}")
            return False

        # Получаем список изображений из папки, если она указана
        if images is None and IMAGES_FOLDER and IMAGES_FOLDER.exists():
            images = list(IMAGES_FOLDER.glob('*.*'))
            images = [img for img in images if
                      img.suffix.lower() in ['.jpg', '.jpeg', '.png']]
            logger.info(f"Найдено {len(images)} изображений для отправки")

        # Получаем отформатированные свободные даты на 3 месяца вперед
        free_dates_message = await format_free_dates_message(bookings)

        if "нет свободных дат" in free_dates_message:
            logger.info(f"Нет свободных дат для объекта {title} на ближайшие 3 месяца")
            return False

        # Формируем сообщение
        message = (
            f"Аренда квартиры в новом комплексе {title} в 400м от пляжа Най Янг\n"
            "10 минут езды от аэропорта!\n"
            "🏡 1BR 36м2, 3й этаж, вид на бассейн\n\n"
            "🗝️Собственник!\n\n"
            "СВОБОДНЫЕ ДЛЯ БРОНИРОВАНИЯ ДАТЫ (ближайшие 3 месяца):\n\n"
            f"{free_dates_message}\n\n"
            "⚠️Есть и другие варианты, спрашивайте в ЛС."
        )

        # Для тестирования выводим сообщение в консоль
        print("=" * 80)
        print("СООБЩЕНИЕ ДЛЯ ОТПРАВКИ:")
        print("=" * 80)
        print(f"Чат ID: {chat_id}")
        print(f"Объект: {title}")
        print(f"CSV файл: {csv_file_path}")
        print("=" * 80)
        print(message)
        print("=" * 80)

        if images:
            print(f"Изображения для отправки ({len(images)} шт.):")
            for img in images:
                print(f"  - {img}")


        # РЕАЛЬНАЯ ОТПРАВКА ЧЕРЕЗ TelegramSender
        print("=" * 80)
        print("ВЫПОЛНЯЕТСЯ РЕАЛЬНАЯ ОТПРАВКА В TELEGRAM...")
        print("=" * 80)

        sender = TelegramSender()

        # Преобразуем пути к изображениям в строки, если есть
        image_paths = None
        if images:
            image_paths = [str(img) for img in images]

        # Отправляем сообщение
        result = await sender.send_message_async(
            channel_name=chat_id,
            message=message,
            media_files=image_paths
        )

        if result:
            logger.info(f"Сообщение успешно отправлено в чат {chat_id}")
            print(f"✅ Сообщение успешно отправлено в {chat_id}")
        else:
            logger.error(f"Ошибка отправки сообщения в чат {chat_id}")
            print(f"❌ Ошибка отправки сообщения в {chat_id}")

        return result

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений: {str(e)}",
                     exc_info=True)
        print(f"❌ Критическая ошибка: {str(e)}")
        return False


async def main():
    """Основная функция со статичными данными для тестирования"""

    # === СТАТИЧНЫЕ ДАННЫЕ ДЛЯ ТЕСТИРОВАНИЯ ===
    chat_id = "@bookind_data"  # Тестовый канал/бот для проверки
    title = "Halo"  # Название объекта
    csv_file = BOOKING_DATA_DIR  # Путь к CSV файлу

    print("=== ЗАПУСК С ТЕСТОВЫМИ ДАННЫМИ ===")
    print(f"Чат ID: {chat_id}")
    print(f"Объект: {title}")
    print(f"CSV файл: {csv_file}")
    print("Период: от текущей даты + 3 месяца вперед")
    print()

    # Проверяем существование CSV файла
    if not Path(csv_file).exists():
        print(f"ОШИБКА: CSV файл не найден: {csv_file}")
        print("Убедитесь, что файл существует и путь указан правильно")
        return False


    # Запускаем отправку
    result = await send_to_specific_chat(chat_id, title, csv_file)

    print(f"Результат тестирования: {'УСПЕШНО' if result else 'ОШИБКА'}")

    return result


if __name__ == "__main__":
    # Просто запускаем main с забитыми данными
    asyncio.run(main())