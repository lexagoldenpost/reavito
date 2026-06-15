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

# Определяем путь к папке booking относительно корня проекта
TASK_DATA_DIR = PROJECT_ROOT / Config.TASK_DATA_DIR

# ID чатов для отправки уведомлений
TELEGRAM_CHAT_IDS = Config.TELEGRAM_CHAT_NOTIFICATION_ID


async def initialize_telegram_client():
    """Инициализирует Telegram клиент с существующей сессией"""
    try:
        # Пробуем использовать существующее подключение
        if await telegram_client.ensure_connection():
            logger.info("✅ Используем существующую сессию Telegram")
            return True

        # Если не удалось, пробуем переподключиться
        logger.warning(
            "⚠️ Существующая сессия недоступна, пробуем переподключиться...")
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

            # Получаем реальные названия колонок из заголовка
            fieldnames = reader.fieldnames
            logger.info(f"CSV fieldnames: {fieldnames}")

            for row in reader:
                try:
                    last_send_str = row.get('Время последней отправки', '').strip()
                    last_send = None
                    if last_send_str:
                        try:
                            # Парсим дату из строки формата "YYYY-MM-DD HH:MM:SS"
                            last_send = datetime.strptime(last_send_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            try:
                                # Парсим дату из строки формата "DD.MM.YYYY HH:MM:SS"
                                last_send = datetime.strptime(last_send_str,
                                                              "%d.%m.%Y %H:%M:%S")
                            except ValueError:
                                try:
                                    # Парсим дату из строки формата "DD.MM.YYYY" (без времени)
                                    last_send = datetime.strptime(last_send_str, "%d.%m.%Y")
                                except ValueError:
                                    logger.warning(
                                        f"Could not parse last_send date: {last_send_str}")

                    chat_data = {
                        'chat_name': row['Наименование чата'].strip(),
                        'send_frequency': int(
                            row['Срок в днях меньше которого не отправляем'].strip()),
                        'accepts_images': row[
                                              'Картинки принимает (Да/Нет)'].strip().lower() == 'да',
                        'channel_name': row['Название канала'].strip(),
                        'chat_object': row.get('Объект', '').strip(),
                        'last_send': last_send,
                        'last_message_id': row.get('ИД последнего сообщения', '').strip(),
                        'message_count_after_last': row.get(
                            'Количество сообщение после последней публикации', '').strip(),
                        '_sync_id': row['_sync_id'].strip()
                    }
                    chats.append(chat_data)
                    logger.debug(
                        f"Loaded chat: {chat_data['chat_name']}, last_send: {last_send}")

                except KeyError as e:
                    logger.error(f"Missing column in CSV: {e}")
                    continue
                except ValueError as e:
                    logger.error(
                        f"Error parsing data for chat {row.get('Наименование чата', 'unknown')}: {e}")
                    continue

        logger.info(f"Loaded {len(chats)} chats from CSV")
    except Exception as e:
        logger.error(f"Error loading chats from CSV: {e}", exc_info=True)

    return chats


def save_chats_to_csv(chats):
    """Сохраняем обновленные данные в CSV"""
    try:
        csv_file = TASK_DATA_DIR / "channels.csv"

        # Читаем текущую структуру файла
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames

        # Обновляем данные
        updated_rows = []
        for chat in chats:
            # Форматируем дату в единый формат "YYYY-MM-DD HH:MM:SS"
            last_send_formatted = ''
            if chat['last_send']:
                last_send_formatted = chat['last_send'].strftime("%Y-%m-%d %H:%M:%S")

            row = {
                'Наименование чата': chat['chat_name'],
                'Срок в днях меньше которого не отправляем': str(
                    chat['send_frequency']),
                'Картинки принимает (Да/Нет)': 'Да' if chat[
                    'accepts_images'] else 'Нет',
                'Название канала': chat['channel_name'],
                'Время последней отправки': last_send_formatted,
                'Объект': chat.get('chat_object', ''),
                'ИД последнего сообщения': chat.get('last_message_id', ''),
                'Количество сообщение после последней публикации': chat.get(
                    'message_count_after_last', ''),
                '_sync_id': chat['_sync_id']
            }
            updated_rows.append(row)

        # Записываем обратно
        with open(csv_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

        logger.info(f"Successfully updated {len(chats)} chats in CSV")

        # Синхронизируем с Google Sheets
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
    Возвращает: (last_message_id, difference) где difference - число или None при ошибке
    """
    try:
        if not stored_message_id:
            logger.warning(f"Для канала {chat_name} отсутствует stored_message_id")
            return None, None

        # Используем единого клиента
        if not await telegram_client.ensure_connection():
            logger.error(f"Нет подключения для канала {chat_name}")
            return None, None

        # Получаем entity канала через единый кэшированный метод
        entity = await telegram_client.get_entity_cached(chat_name)
        if not entity:
            logger.error(f"Канал {chat_name} не найден")
            return None, None

        # Получаем последнее сообщение через telethon
        messages = await telegram_client.client.get_messages(entity, limit=1)
        if not messages:
            logger.warning(f"В канале {chat_name} нет сообщений")
            return None, None

        last_message_id = messages[0].id

        try:
            stored_id = int(stored_message_id)
            difference = last_message_id - stored_id
            return last_message_id, difference
        except ValueError:
            logger.error(f"Ошибка формата ID для канала {chat_name}: stored_message_id='{stored_message_id}'")
            return None, None

    except asyncio.TimeoutError:
        logger.error(f"Таймаут при получении ID сообщения для {chat_name}")
        return None, None
    except Exception as e:
        logger.error(f"Ошибка при получении ID сообщения для {chat_name}: {str(e)}", exc_info=True)
        return None, None


async def send_telegram_notification(http_session, chat_data: dict, message_count: int):
    """
    Отправляет уведомление в Telegram о большом количестве новых сообщений
    """
    try:
        # Формируем сообщение
        notification_title = (
            "⚠️ <b>ВНИМАНИЕ: МНОГО НОВЫХ СООБЩЕНИЙ В КАНАЛЕ</b> ⚠️\n\n"
            f"📢 <b>Канал:</b> {chat_data['chat_name']}\n"
            f"🏠 <b>Объект:</b> {chat_data.get('chat_object', 'Не указан')}\n"
            f"📊 <b>Новых сообщений:</b> {message_count}\n"
            f"⏰ <b>Пороговое значение:</b> 8\n\n"
            "<b>Рекомендация:</b> Требуется проверка и возможная публикация в чатах бронирований."
        )

        detailed_info = (
            f"📝 <b>Детали:</b>\n"
            f"• С момента последней отправки прошло: {message_count} дней\n"
            f"• Минимальный срок для отправки: {chat_data['send_frequency']} дней\n"
            f"• Канал принимает изображения: {'Да' if chat_data['accepts_images'] else 'Нет'}\n"
            f"• Название канала: {chat_data['channel_name']}\n\n"
            f"<i>Для отправки сообщения используйте основной бот или выполните ручную проверку.</i>"
        )

        # Отправляем уведомления во все настроенные чаты
        for chat_id in TELEGRAM_CHAT_IDS:
            try:
                await send_message(http_session, chat_id, notification_title)
                await send_message(http_session, chat_id, detailed_info)
                logger.info(f"✅ Уведомление отправлено в чат {chat_id} для канала {chat_data['chat_name']}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки в чат {chat_id}: {e}")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при формировании уведомления для {chat_data['chat_name']}: {e}")
        return False


async def check_and_send_notification(chat_data: dict, old_message_count, new_message_count):
    """
    Проверяет условия и отправляет уведомление если:
    1. Новое количество сообщений > 8
    2. Старое значение было заполнено (не пустое)
    3. С момента последней отправки прошло больше минимального срока
    """
    try:
        # Проверяем что новое значение - число
        try:
            new_count = int(new_message_count)
        except (ValueError, TypeError):
            logger.debug(f"Новое значение не является числом для {chat_data['chat_name']}: {new_message_count}")
            return False

        # Условие 1: новое количество > 8
        if new_count <= 8:
            logger.debug(
                f"Количество сообщений ({new_count}) <= 8 для {chat_data['chat_name']}, уведомление не требуется")
            return False

        # Условие 2: было ли старое значение заполнено
        if not old_message_count or str(old_message_count).strip() == '':
            logger.info(f"Для {chat_data['chat_name']} старое значение не было заполнено, пропускаем уведомление")
            return False

        # Условие 3: проверяем время с последней отправки
        last_send = chat_data.get('last_send')
        if last_send:
            days_since_last_send = (datetime.now() - last_send).days
            min_days = chat_data.get('send_frequency', 7)

            if days_since_last_send < min_days:
                logger.info(
                    f"Для {chat_data['chat_name']} с момента последней отправки прошло {days_since_last_send} дней, "
                    f"что меньше минимального срока {min_days} дней. Уведомление не требуется."
                )
                return False
        else:
            logger.debug(f"Для {chat_data['chat_name']} нет даты последней отправки")

        # Все условия выполнены - отправляем уведомление
        logger.info(
            f"🔔 Можно сделать рассылку для чата {chat_data['chat_name']}: "
            f"новых сообщений={new_count}, старое значение={old_message_count}"
        )

        async with aiohttp.ClientSession() as session:
            await send_telegram_notification(session, chat_data, new_count)

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке уведомления для {chat_data['chat_name']}: {e}")
        return False


async def process_chat_update(chat):
    """
    Обрабатывает обновление данных для одного канала
    """
    try:
        chat_name = chat['chat_name']
        stored_message_id = chat['last_message_id']
        old_value = chat.get('message_count_after_last', '')
        old_value_str = str(old_value) if old_value else ''

        logger.info(f"Processing chat: {chat_name}")

        # Получаем разницу ID сообщений
        last_message_id, difference = await get_last_message_id_difference(
            chat_name, stored_message_id
        )

        # Обновляем данные чата только если получили корректную разницу (число)
        if difference is not None and isinstance(difference, int):
            new_value = str(difference)
            chat['message_count_after_last'] = new_value
            # Также обновляем ID последнего сообщения, если нужно
            if last_message_id is not None:
                chat['last_message_id'] = str(last_message_id)
            logger.info(f"✅ Обновлен {chat_name}: было '{old_value_str}', стало '{new_value}'")

            # Проверяем нужно ли отправить уведомление
            await check_and_send_notification(chat, old_value_str, new_value)

        else:
            # При ошибке оставляем старое значение, ничего не записываем в CSV
            # Но в логе ошибка уже залогирована в get_last_message_id_difference
            logger.error(f"⚠️ Не удалось обновить {chat_name}, сохраняем старое значение: '{old_value_str}'")

        return chat

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при обработке канала {chat['chat_name']}: {e}", exc_info=True)
        return chat  # Возвращаем исходный чат без изменений


async def update_message_counts():
    """
    Основная функция для обновления счетчиков сообщений
    """
    logger.info("Starting update of message counts...")

    # Инициализируем Telegram клиент
    if not await initialize_telegram_client():
        logger.error("❌ Не удалось инициализировать Telegram клиент")
        return

    # Загружаем чаты из CSV
    all_chats = load_chats_from_csv()

    if not all_chats:
        logger.error("No chats loaded from CSV")
        return

    # Фильтруем чаты: у которых есть ИД последнего сообщения
    # и время последней публикации меньше 8 дней
    target_chats = []
    current_time = datetime.now()

    for chat in all_chats:
        # Проверяем наличие ID последнего сообщения
        if not chat.get('last_message_id'):
            logger.debug(f"Chat {chat.get('chat_name')} пропущен: нет ID последнего сообщения")
            continue

        # Проверяем время последней отправки (меньше 8 дней)
        last_send = chat.get('last_send')
        if last_send:
            days_diff = (current_time - last_send).days
            if days_diff < 8:
                target_chats.append(chat)
            else:
                logger.debug(f"Chat {chat.get('chat_name')} пропущен: прошло {days_diff} дней (>7)")
        else:
            # Если нет времени отправки, но есть ID сообщения - включаем
            target_chats.append(chat)
            logger.debug(f"Chat {chat.get('chat_name')} включен: нет времени последней отправки")

    logger.info(f"Found {len(target_chats)} chats to update")

    if not target_chats:
        logger.info("No chats meet the criteria for update")
        return

    # Предварительно загружаем entity для всех целевых чатов через единый метод
    logger.info("Preloading entity cache for target chats...")
    for chat in target_chats:
        await telegram_client.get_entity_cached(chat['chat_name'])

    # Даем немного времени для загрузки кэша
    await asyncio.sleep(2)

    # Создаем задачи для параллельной обработки
    tasks = []
    for chat in target_chats:
        tasks.append(process_chat_update(chat))

    # Выполняем все задачи параллельно с ограничением
    if tasks:
        semaphore = asyncio.Semaphore(3)  # Максимум 3 одновременных запроса

        async def bounded_task(task):
            async with semaphore:
                return await task

        bounded_tasks = [bounded_task(task) for task in tasks]
        results = await asyncio.gather(*bounded_tasks, return_exceptions=True)

        # Собираем обновленные чаты
        updated_chats = []
        error_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Исключение при обработке канала {target_chats[i]['chat_name']}: {result}")
                # Сохраняем оригинальный чат в случае ошибки
                updated_chats.append(target_chats[i])
                error_count += 1
            elif result:
                updated_chats.append(result)
            else:
                # Сохраняем оригинальный чат если результат None
                updated_chats.append(target_chats[i])
                error_count += 1

        # Обновляем основной список чатов
        chat_dict = {chat['_sync_id']: chat for chat in all_chats}
        for updated_chat in updated_chats:
            chat_dict[updated_chat['_sync_id']] = updated_chat

        # Сохраняем все чаты обратно в CSV (только с числовыми значениями)
        save_chats_to_csv(list(chat_dict.values()))

        logger.info(f"✅ Обновление завершено. Успешно: {len(target_chats) - error_count}, Ошибок: {error_count}")

    else:
        logger.info("No tasks to process")


async def main():
    """Основная функция для запуска по расписанию"""
    try:
        logger.info("Starting scheduled update of message counts...")

        # Инициализируем Telegram клиент
        if not await initialize_telegram_client():
            logger.error("Failed to authenticate Telegram client")
            return

        # Предварительно загружаем entity кэш через единый метод
        logger.info("Preloading entity cache...")
        await telegram_client.preload_entity_cache()

        # Выполняем обновление
        await update_message_counts()

        logger.info("Scheduled update completed successfully")

    except Exception as e:
        logger.error(f"Error in main scheduled task: {e}", exc_info=True)


if __name__ == "__main__":
    # Запуск напрямую (для тестирования)
    asyncio.run(main())