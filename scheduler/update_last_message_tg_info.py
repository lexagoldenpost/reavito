# scheduler/update_last_message_tg_info.py
from datetime import datetime
import csv
import os
import asyncio
import aiohttp
from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.telegram_client import telegram_client
from telega.telegram_utils import TelegramUtils
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
from telega.tg_notifier import send_message

logger = setup_logger("update_last_message_tg_info")

TASK_DATA_DIR = PROJECT_ROOT / Config.TASK_DATA_DIR

TELEGRAM_CHAT_IDS = Config.TELEGRAM_CHAT_NOTIFICATION_ID


async def initialize_telegram_client():
    """Инициализирует Telegram клиент с существующей сессией"""
    try:
        if await telegram_client.ensure_connection():
            logger.info("✅ Используем существующую сессию Telegram")
            return True

        logger.warning("⚠️ Существующая сессия недоступна, пробуем переподключиться...")
        telegram_client.clear_entity_cache()
        if await telegram_client.ensure_connection():
            logger.info("✅ Переподключение успешно")
            return True

        logger.error("❌ Не удалось инициализировать Telegram клиент")
        return False

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Telegram клиента: {e}")
        return False


def load_chats_from_csv():
    """Загрузка данных о чатах из CSV файла"""
    chats = []
    csv_file = TASK_DATA_DIR / "channels.csv"

    if not os.path.exists(csv_file):
        logger.error(f"CSV file {csv_file} not found")
        return chats

    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
            logger.info(f"CSV fieldnames: {fieldnames}")

            for row in reader:
                try:
                    last_send_str = row.get('Время последней отправки', '').strip()
                    last_send = None
                    if last_send_str:
                        try:
                            last_send = datetime.strptime(last_send_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            try:
                                last_send = datetime.strptime(last_send_str, "%d.%m.%Y %H:%M:%S")
                            except ValueError:
                                try:
                                    last_send = datetime.strptime(last_send_str, "%d.%m.%Y")
                                except ValueError:
                                    logger.warning(f"Could not parse last_send date: {last_send_str}")

                    chat_data = {
                        'chat_name': row['Наименование чата'].strip(),
                        'send_frequency': int(row['Срок в днях меньше которого не отправляем'].strip()),
                        'accepts_images': row['Картинки принимает (Да/Нет)'].strip().lower() == 'да',
                        'channel_name': row['Название канала'].strip(),
                        'chat_object': row.get('Объект', '').strip(),
                        'last_send': last_send,
                        'last_message_id': row.get('ИД последнего сообщения', '').strip(),
                        'message_count_after_last': row.get('Количество сообщение после последней публикации',
                                                            '').strip(),
                        '_sync_id': row['_sync_id'].strip()
                    }
                    chats.append(chat_data)
                    logger.debug(f"Loaded chat: {chat_data['chat_name']}, last_send: {last_send}")

                except KeyError as e:
                    logger.error(f"Missing column in CSV: {e}")
                    continue
                except ValueError as e:
                    logger.error(f"Error parsing data for chat {row.get('Наименование чата', 'unknown')}: {e}")
                    continue

        logger.info(f"Loaded {len(chats)} chats from CSV")
    except Exception as e:
        logger.error(f"Error loading chats from CSV: {e}", exc_info=True)

    return chats


def save_chats_to_csv(chats):
    """Сохраняем обновленные данные в CSV"""
    try:
        csv_file = TASK_DATA_DIR / "channels.csv"

        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames

        updated_rows = []
        for chat in chats:
            last_send_formatted = ''
            if chat['last_send']:
                last_send_formatted = chat['last_send'].strftime("%Y-%m-%d %H:%M:%S")

            row = {
                'Наименование чата': chat['chat_name'],
                'Срок в днях меньше которого не отправляем': str(chat['send_frequency']),
                'Картинки принимает (Да/Нет)': 'Да' if chat['accepts_images'] else 'Нет',
                'Название канала': chat['channel_name'],
                'Время последней отправки': last_send_formatted,
                'Объект': chat.get('chat_object', ''),
                'ИД последнего сообщения': chat.get('last_message_id', ''),  # ⚠️ НЕ МЕНЯЕМ
                'Количество сообщение после последней публикации': chat.get('message_count_after_last', ''),
                '_sync_id': chat['_sync_id']
            }
            updated_rows.append(row)

        with open(csv_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

        logger.info(f"Successfully updated {len(chats)} chats in CSV")

        sync_manager = GoogleSheetsCSVSync()
        sync_success = sync_manager.sync_sheet(
            sheet_name="Отправка бронирований",
            direction='csv_to_google'
        )

        if sync_success:
            logger.info("Successfully synchronized with Google Sheets")
        else:
            logger.error("Failed to synchronize with Google Sheets")

    except Exception as e:
        logger.error(f"Error saving chats to CSV: {e}")


async def get_last_message_id_difference(chat_name, stored_message_id):
    """
    Получаем разницу между последним сообщением в канале и сохраненным ID
    Возвращает: difference (число) или None при ошибке
    НЕ обновляет last_message_id в CSV
    """
    try:
        if not stored_message_id:
            logger.warning(f"Для канала {chat_name} отсутствует stored_message_id")
            return None

        if not await telegram_client.ensure_connection():
            logger.error(f"Нет подключения для канала {chat_name}")
            return None

        entity = await telegram_client.get_entity_cached(chat_name)
        if not entity:
            logger.error(f"Канал {chat_name} не найден")
            return None

        messages = await telegram_client.client.get_messages(entity, limit=1)
        if not messages:
            logger.warning(f"В канале {chat_name} нет сообщений")
            return None

        last_message_id = messages[0].id

        try:
            stored_id = int(stored_message_id)
            difference = last_message_id - stored_id
            logger.info(
                f"📊 {chat_name}: last_message_id={last_message_id}, stored_id={stored_id}, difference={difference}")
            return difference
        except ValueError:
            logger.error(f"Ошибка формата ID для канала {chat_name}: stored_message_id='{stored_message_id}'")
            return None

    except asyncio.TimeoutError:
        logger.error(f"Таймаут при получении ID сообщения для {chat_name}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении ID сообщения для {chat_name}: {str(e)}", exc_info=True)
        return None


def check_conditions(chat_data, difference) -> dict:
    """
    Проверяет условия для отбора каналов (как в PHP)
    """
    result = {
        'passed': False,
        'object_match': False,
        'days_condition': False,
        'time_condition': False,
        'message_count': difference,
        'days_since_last': None
    }

    # 1. Проверка объекта
    chat_object = chat_data.get('chat_object', '').strip()
    result['object_match'] = chat_object == '' or chat_object == "Halo Title"

    # 2. Проверка количества сообщений (> 8)
    result['days_condition'] = difference > 8 if difference is not None else False
    result['message_count'] = difference if difference is not None else 0

    # 3. Проверка времени последней отправки
    last_send = chat_data.get('last_send')
    min_days = chat_data.get('send_frequency', 7)

    if last_send is None:
        result['time_condition'] = True
        result['days_since_last'] = None
    else:
        current_time = datetime.now()
        if last_send > current_time:
            result['time_condition'] = False
            result['days_since_last'] = 0
        else:
            days_since_last = (current_time - last_send).days
            result['days_since_last'] = days_since_last
            result['time_condition'] = days_since_last > min_days

    result['passed'] = (
            result['object_match'] and
            result['days_condition'] and
            result['time_condition']
    )

    return result


async def send_summary_report(http_session, matched_channels: list):
    """Отправляет лаконичный отчет со списком каналов для рассылки"""
    if not matched_channels:
        message = (
            "📊 <b>Отчет по обновлению счетчиков</b>\n\n"
            "✅ Данные обновлены\n"
            "📭 Каналов для рассылки: <b>0</b>\n"
            "⏰ Все каналы в норме"
        )
        for chat_id in TELEGRAM_CHAT_IDS:
            try:
                await send_message(http_session, chat_id, message)
                logger.info(f"✅ Отчет отправлен в {chat_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")
        return

    total = len(matched_channels)

    header = (
        "📊 <b>Каналы для рассылки</b>\n\n"
        f"📢 Найдено каналов: <b>{total}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    channels_list = []
    for i, chat in enumerate(matched_channels, 1):
        chat_name = chat.get('channel_name', chat.get('chat_name', 'Без названия'))
        message_count = chat.get('_message_count', 0)
        days_since = chat.get('_days_since', '—')
        accepts_images = '📷' if chat.get('accepts_images') else '📝'

        if len(chat_name) > 35:
            chat_name = chat_name[:32] + '...'

        channels_list.append(
            f"{i}. {accepts_images} <b>{chat_name}</b>\n"
            f"   📨 {message_count} новых | ⏳ {days_since} дней"
        )

    full_message = header + "\n".join(channels_list)

    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            await send_message(http_session, chat_id, full_message)
            logger.info(f"✅ Отчет отправлен в {chat_id} ({total} каналов)")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в {chat_id}: {e}")


async def process_chat_update(chat):
    """
    Обрабатывает обновление данных для одного канала
    ТОЛЬКО обновляет message_count_after_last
    НЕ обновляет ИД последнего сообщения
    """
    try:
        chat_name = chat['chat_name']
        stored_message_id = chat['last_message_id']
        old_value = chat.get('message_count_after_last', '')
        old_value_str = str(old_value) if old_value else ''

        logger.info(f"Processing chat: {chat_name}")

        # Получаем разницу ID сообщений (НО НЕ ОБНОВЛЯЕМ ID)
        difference = await get_last_message_id_difference(
            chat_name, stored_message_id
        )

        # Обновляем только Количество сообщение после последней публикации
        if difference is not None and isinstance(difference, int):
            new_value = str(difference)
            chat['message_count_after_last'] = new_value
            # ⚠️ НЕ обновляем last_message_id - его обновляют только при реальной отправке
            logger.info(f"✅ Обновлен {chat_name}: было '{old_value_str}', стало '{new_value}'")
        else:
            logger.error(f"⚠️ Не удалось обновить {chat_name}, сохраняем старое значение: '{old_value_str}'")

        return chat

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при обработке канала {chat['chat_name']}: {e}", exc_info=True)
        return chat


async def update_message_counts():
    """
    Основная функция для обновления счетчиков сообщений
    """
    logger.info("Starting update of message counts...")

    if not await initialize_telegram_client():
        logger.error("❌ Не удалось инициализировать Telegram клиент")
        return

    all_chats = load_chats_from_csv()

    if not all_chats:
        logger.error("No chats loaded from CSV")
        return

    # Обновляем все чаты, у которых есть ИД последнего сообщения
    target_chats = []
    for chat in all_chats:
        if chat.get('last_message_id'):
            target_chats.append(chat)

    logger.info(f"Found {len(target_chats)} chats to update")

    if not target_chats:
        logger.info("No chats meet the criteria for update")
        return

    logger.info("Preloading entity cache for target chats...")
    for chat in target_chats:
        await telegram_client.get_entity_cached(chat['chat_name'])

    await asyncio.sleep(2)

    tasks = [process_chat_update(chat) for chat in target_chats]

    if tasks:
        semaphore = asyncio.Semaphore(3)

        async def bounded_task(task):
            async with semaphore:
                return await task

        bounded_tasks = [bounded_task(task) for task in tasks]
        results = await asyncio.gather(*bounded_tasks, return_exceptions=True)

        updated_chats = []
        matched_channels = []
        error_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Исключение при обработке канала {target_chats[i]['chat_name']}: {result}")
                updated_chats.append(target_chats[i])
                error_count += 1
            elif result:
                updated_chats.append(result)

                # Проверяем условия для отчета
                difference = int(result.get('message_count_after_last', 0))
                conditions = check_conditions(result, difference)
                if conditions['passed']:
                    result['_message_count'] = conditions['message_count']
                    result['_days_since'] = conditions['days_since_last'] or '—'
                    matched_channels.append(result)
                    logger.info(f"✅ Канал в выборке: {result['chat_name']} ({conditions['message_count']} новых)")
            else:
                updated_chats.append(target_chats[i])
                error_count += 1

        chat_dict = {chat['_sync_id']: chat for chat in all_chats}
        for updated_chat in updated_chats:
            chat_dict[updated_chat['_sync_id']] = updated_chat

        save_chats_to_csv(list(chat_dict.values()))

        logger.info(f"✅ Обновление завершено. Успешно: {len(target_chats) - error_count}, Ошибок: {error_count}")
        logger.info(f"📊 Каналов для рассылки: {len(matched_channels)}")

        # Отправляем отчет
        async with aiohttp.ClientSession() as session:
            await send_summary_report(session, matched_channels)

    else:
        logger.info("No tasks to process")


async def main():
    """Основная функция для запуска по расписанию"""
    try:
        logger.info("Starting scheduled update of message counts...")

        if not await initialize_telegram_client():
            logger.error("Failed to authenticate Telegram client")
            return

        logger.info("Preloading entity cache...")
        await telegram_client.preload_entity_cache()

        await update_message_counts()

        logger.info("Scheduled update completed successfully")

    except Exception as e:
        logger.error(f"Error in main scheduled task: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())