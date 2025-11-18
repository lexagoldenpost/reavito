# send_bookings.py
from datetime import datetime
import csv
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.booking_objects import PROJECT_ROOT
from telega.send_tg_reklama import TelegramSender
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync


logger = setup_logger("send_bookings")

# Добавляем префиксы для callback-данных
CALLBACK_PREFIX = "sb_"  # sb = send_bookings
SEND_TO_CHAT = f"{CALLBACK_PREFIX}send_to"
REFRESH_CHATS = f"{CALLBACK_PREFIX}refresh"

# Определяем путь к папке booking относительно корня проекта
TASK_DATA_DIR = PROJECT_ROOT / Config.TASK_DATA_DIR

# Глобальный словарь для хранения времени последней отправки
last_send_times = {}


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
                            # Парсим дату из строки формата "YYYY-MM-DD HH:MM:SS" или "DD.MM.YYYY"
                            last_send = datetime.strptime(last_send_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            try:
                                last_send = datetime.strptime(last_send_str, "%d.%m.%Y %H:%M:%S")
                            except ValueError:
                                logger.warning(f"Could not parse last_send date: {last_send_str}")

                    chat_data = {
                        'chat_name': row['Наименование чата'].strip(),
                        'send_frequency': int(row['Срок в днях меньше которого не отправляем '].strip()),
                        'accepts_images': row['Картинки принимает (Да/Нет)'].strip().lower() == 'да',
                        'channel_name': row['Название канала'].strip(),
                        'chat_object': row.get('Объект чата', '').strip(),
                        'last_send': last_send,
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


def save_last_send_time(chat_name):
    """Сохраняем время последней отправки для чата в CSV"""
    try:
        csv_file = TASK_DATA_DIR / "channels.csv"

        # Читаем все данные
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            fieldnames = reader.fieldnames

        # Обновляем время для конкретного чата
        for row in rows:
            if row['Наименование чата'].strip() == chat_name:
                row['Время последней отправки'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break

        # Записываем обратно
        with open(csv_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.debug(f"Saved last send time for {chat_name} in CSV")

        # Обновляем в гугл таблице
        sync_manager = GoogleSheetsCSVSync()
        sync_success = sync_manager.sync_sheet(sheet_name="Отправка бронирований", direction='csv_to_google')
        if not sync_success:
            raise RuntimeError("Синхронизация завершилась со статусом False")

    except Exception as e:
        logger.error(f"Error saving last send time to CSV: {e}")


def get_last_send_time(chat_name):
    """Получаем время последней отправки для чата из CSV"""
    try:
        chats = load_chats_from_csv()
        for chat in chats:
            if chat['chat_name'] == chat_name:
                return chat['last_send']
    except Exception as e:
        logger.error(f"Error getting last send time from CSV: {e}")

    return None

async def send_bookings_handler(update, context):
    """Обработчик для рассылки бронирований"""
    logger.info("Entered send_bookings_handler")
    try:
        if update.callback_query:
            logger.debug(f"Received callback query: {update.callback_query.data}")
            # Проверяем, что callback относится к этому модулю
            if update.callback_query.data.startswith(CALLBACK_PREFIX):
                logger.debug("Callback belongs to this module, processing...")
                return await handle_callback(update, context)
            else:
                logger.debug("Callback not for this module, skipping...")
                # Пропускаем callback, если он не для этого модуля
                return
        elif update.message:
            logger.debug(f"Received message: {update.message.text}")
            return await handle_message(update, context)
        else:
            logger.error("Unknown update type in send_bookings_handler")

    except Exception as e:
        logger.error(f"Error in send_bookings_handler: {e}", exc_info=True)
        error_message = "Произошла ошибка при обработке запроса"
        if hasattr(context, 'user_data'):
            context.user_data['step'] = 1  # Сбрасываем step при ошибке
        await send_reply(update, error_message)


async def handle_message(update, context):
    if update.message.text.strip().lower() == '/exit':
        if hasattr(context, 'user_data'):
            context.user_data.clear()
        await send_reply(update, "Сессия завершена. Начните заново.")
        return

    if not hasattr(context, 'user_data') or 'step' not in context.user_data:
        await show_available_chats(update, context)
        context.user_data['step'] = 1


async def handle_callback(update, context):
    """Обработка нажатия на кнопку"""
    logger.info("Entered handle_callback")
    query = update.callback_query
    await query.answer()
    logger.debug(f"Callback query answered: {query.data}")

    try:
        if query.data.startswith(SEND_TO_CHAT):  # Проверяем конкретный префикс для действий
            logger.info(f"Processing SEND_TO_CHAT action: {query.data}")
            # Извлекаем chat_name из callback_data (формат: "sb_send_to_STR")
            logger.debug(f"Extracting chat_name from {query.data}")
            parts = query.data.split('_')
            if len(parts) >= 3:
                chat_name = '_'.join(parts[3:])  # Объединяем оставшиеся части на случай если chat_name содержит _
                logger.info(f"Preparing to send notification to chat_name: {chat_name}")
                await send_notification_to_chat(update, context, chat_name)
            else:
                logger.error(f"Invalid callback_data format: {query.data}")
                if hasattr(context, 'user_data'):
                    context.user_data['step'] = 1  # Сбрасываем step при ошибке
                await send_reply(update, "Ошибка: неверный формат запроса \nВыход /exit")
        elif query.data == REFRESH_CHATS:
            logger.info("Processing REFRESH_CHATS action")
            await show_available_chats(update, context)
        else:
            logger.debug(f"Ignoring callback with data: {query.data}")
            # Если callback не относится к этому модулю, пропускаем
            return
    except Exception as e:
        logger.error(f"Error in handle_callback: {e}", exc_info=True)
        await send_reply(update, "❌ Ошибка. Используйте /exit для сброса.")
        if hasattr(context, 'user_data'):
            context.user_data.clear()
    finally:
        try:
            logger.debug("Attempting to delete callback message")
            await query.message.delete()
            logger.debug("Callback message deleted successfully")
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")


async def show_available_chats(update, context):
    """Показать доступные для рассылки чаты (на основе CSV)"""
    logger.info("Entered show_available_chats")
    try:
        current_date = datetime.now()
        logger.debug(f"Current date: {current_date}")

        # Загружаем чаты из CSV
        all_chats = load_chats_from_csv()
        if not all_chats:
            logger.info("No chats found in CSV")
            if hasattr(context, 'user_data'):
                context.user_data['step'] = 1
            await send_reply(update, "Нет данных о чатах в CSV файле \nВыход /exit")
            return

        # Фильтруем доступные чаты
        available_chats = []
        for chat in all_chats:
            last_send = get_last_send_time(chat['chat_name'])

            # Проверяем, можно ли отправить рассылку
            if last_send is None:
                # Если никогда не отправляли - доступен
                available_chats.append(chat)
            else:
                # Проверяем частоту отправки
                days_passed = (current_date - last_send).days
                if days_passed > chat['send_frequency']:
                    available_chats.append(chat)

        logger.debug(f"Found {len(available_chats)} available chats")

        if not available_chats:
            logger.info("No available chats found")
            if hasattr(context, 'user_data'):
                context.user_data['step'] = 1
            await send_reply(update, "Нет чатов, доступных для рассылки в данный момент \nВыход /exit")
            return

        keyboard = []
        for chat in available_chats:
            display_name = chat['channel_name'] if chat['channel_name'] else chat['chat_name']
            chat_info = f"{display_name}"

            if chat['chat_object']:
                chat_info += f" ({chat['chat_object']})"

            last_send = get_last_send_time(chat['chat_name'])
            if last_send:
                last_send_str = last_send.strftime("%d.%m.%Y")
                days_passed = (current_date - last_send).days
                chat_info += f"\nПоследняя: {last_send_str} ({days_passed} дн. назад)"
            else:
                chat_info += "\nРассылка не производилась"

            if chat['send_frequency']:
                chat_info += f" | Частота: {chat['send_frequency']} дн."

            logger.debug(f"Creating button for chat: {chat_info}, {SEND_TO_CHAT}_{chat['chat_name']}")
            button = InlineKeyboardButton(
                text=chat_info,
                callback_data=f"{SEND_TO_CHAT}_{chat['chat_name']}"
            )
            keyboard.append([button])

        refresh_button = InlineKeyboardButton("🔄 Обновить список", callback_data=REFRESH_CHATS)
        keyboard.append([refresh_button])
        logger.debug("Created all buttons for keyboard")

        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_reply(
            update,
            "Выберите чат для рассылки:",
            reply_markup=reply_markup
        )
        logger.info("Successfully showed available chats")

    except Exception as e:
        logger.error(f"Error in show_available_chats: {e}", exc_info=True)
        if hasattr(context, 'user_data'):
            context.user_data['step'] = 1
        await send_reply(update, "Ошибка при получении списка чатов \nВыход /exit")


async def send_notification_to_chat(update, context, chat_name):
    """Отправка уведомления в конкретный чат"""
    logger.info(f"Entered send_notification_to_chat for chat_name: {chat_name}")
    try:
        # Ищем чат в CSV данных
        all_chats = load_chats_from_csv()
        chat = None
        for c in all_chats:
            if c['chat_name'] == chat_name:
                chat = c
                break

        if not chat:
            logger.error(f"Chat not found in CSV: {chat_name}")
            await send_reply(update, "❌ Чат не найден. Выход /exit")
            if hasattr(context, 'user_data'):
                context.user_data.clear()
            return

        display_name = chat['channel_name'] if chat['channel_name'] else chat['chat_name']
        title = chat['chat_object'] if chat['chat_object'] else "HALO Title"

        logger.info(f"Sending announcement to chat {chat['chat_name']} with object {title}")

        # Используем реальную функцию отправки
        success = await send_to_specific_chat(
            chat_id=chat['chat_name'],  # или используйте chat['chat_object'] если нужно
            title=title
        )

        if success:
            logger.debug("Notification sent successfully, updating last_send")
            save_last_send_time(chat['chat_name'])
            logger.debug("Last send time updated successfully")

            await send_reply(
                update,
                f"✅ Рассылка успешно отправлена в:\n"
                f"Название: {display_name}\n"
                f"Объект: {chat['chat_object'] or 'не указан'}\n"
                f"ID чата: {chat['chat_name']}"
            )
            logger.info("Success notification sent to user")
            if hasattr(context, 'user_data'):
                context.user_data.clear()
        else:
            logger.error(f"Failed to send notification to chat {chat['chat_name']}")
            if hasattr(context, 'user_data'):
                context.user_data['step'] = 1
            await send_reply(
                update,
                f"❌ Ошибка при отправке рассылки в {display_name} \nВыход /exit"
            )

    except Exception as e:
        logger.error(f"Error in send_notification_to_chat: {e}", exc_info=True)
        await send_reply(update, "❌ Критическая ошибка. Сессия сброшена. /exit")
        if hasattr(context, 'user_data'):
            context.user_data.clear()

async def send_reply(update, text, reply_markup=None, parse_mode=None):
    """Универсальная функция отправки сообщения"""
    logger.debug(f"Preparing to send reply with text: {text}")
    try:
        if update.callback_query:
            logger.debug("Sending reply to callback_query")
            await update.callback_query.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif update.message:
            logger.debug("Sending reply to message")
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        logger.debug("Reply sent successfully")
    except Exception as e:
        logger.error(f"Error in send_reply: {e}", exc_info=True)
        raise

async def send_to_specific_chat(chat_id, title):
        """Отправка сообщения в конкретный чат через TelegramSender"""
        try:
            sender = TelegramSender()

            # Формируем сообщение для отправки
            message = f"📢 Уведомление о бронировании\n\n{title}"

            # Отправляем сообщение
            success = await sender.send_message_async(
                channel_identifier=chat_id,
                message=message
            )

            return success

        except Exception as e:
            logger.error(f"Error in send_to_specific_chat: {e}")
            return False