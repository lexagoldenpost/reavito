# add_booking.py
import json
import csv
import os
import uuid
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.command.view_booking import get_file_path

logger = setup_logger("add_booking")

# Состояния для ConversationHandler
SELECTING_OBJECT, FILLING_FORM = range(2)


class AddBookingHandler:
    def __init__(self, bot_instance=None):
        self.csv_file = "citygate_p311.csv"
        self.objects = {
            "citygate_p311": "CityGate P311"
        }
        self.bot = bot_instance
        # URL удаленного веб-сервера с формой бронирования
        self.remote_web_app_url = Config.REMOTE_WEB_APP_URL + Config.REMOTE_WEB_APP_CREATE_BOOKING_URL

    async def start_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса бронирования"""
        logger.info("=== START BOOKING PROCESS ===")
        logger.info(f"User: {update.effective_user.username} (ID: {update.effective_user.id})")

        # Проверка прав доступа через экземпляр бота, если он передан
        if self.bot and not await self.bot.check_user_permission(update):
            logger.warning("User permission denied")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton("🏢 CityGate P311", callback_data="object_citygate_p311")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🏨 *Выберите объект для бронирования:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info("Object selection presented to user")
        return SELECTING_OBJECT

    async def select_object(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора объекта"""
        query = update.callback_query
        await query.answer()

        logger.info(f"=== OBJECT SELECTION ===")
        logger.info(f"User: {query.from_user.username} (ID: {query.from_user.id})")
        logger.info(f"Callback data: {query.data}")

        # Проверка прав доступа
        if self.bot and not await self.bot.check_user_permission(update):
            logger.warning("User permission denied in object selection")
            return ConversationHandler.END

        # Извлекаем object_id из callback_data, убирая префикс "object_"
        callback_data = query.data
        object_id = callback_data.replace("object_", "")

        logger.info(f"Selected object: {object_id}")

        if object_id not in self.objects:
            logger.error(f"Object not found: {object_id}")
            await query.edit_message_text(
                "❌ *Ошибка: объект не найден*",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        context.user_data['selected_object'] = object_id
        context.user_data['object_name'] = self.objects.get(object_id, "Unknown Object")

        logger.info(f"Context user_data updated: {context.user_data}")

        # Используем URL удаленного веб-сервера
        try:
            if not self.remote_web_app_url:
                raise Exception("Remote web app URL not configured")

            # Формируем URL для удаленной формы бронирования
            web_app_url = f"{self.remote_web_app_url}/?object={object_id}&user_id={query.from_user.id}"
            web_app_info = WebAppInfo(url=web_app_url)

            logger.info(f"Web app URL created: {web_app_url}")

            keyboard = [
                [InlineKeyboardButton(
                    "📝 Заполнить форму бронирования",
                    web_app=web_app_info
                )],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_booking")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✅ *Выбран объект: {self.objects[object_id]}*\n\n"
                "Нажмите кнопку ниже чтобы открыть форму бронирования:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

            logger.info("Web app button presented to user")
            return FILLING_FORM

        except Exception as e:
            logger.error(f"Failed to create web app URL: {e}", exc_info=True)
            await query.edit_message_text(
                "❌ *Ошибка подключения к серверу форм*\nПопробуйте позже.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    async def handle_web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка данных из Web App с удаленного сервера"""
        logger.info("=== WEB APP DATA RECEIVED ===")
        logger.info(f"Update: {update}")
        logger.info(f"Update type: {update.update_type}")
        logger.info(
            f"Has web_app_data: {hasattr(update, 'message') and update.message and hasattr(update.message, 'web_app_data')}")

        if update.message and update.message.web_app_data:
            logger.info(f"WebApp data object: {update.message.web_app_data}")
            logger.info(f"Button_text: {update.message.web_app_data.button_text}")

        logger.info(f"User: {update.effective_user.username} (ID: {update.effective_user.id})")

        try:
            # Проверка прав доступа
            if self.bot and not await self.bot.check_user_permission(update):
                logger.warning("User permission denied in web app data handling")
                return ConversationHandler.END

            # Проверяем, что данные действительно есть
            if not update.message or not update.message.web_app_data:
                logger.error("No web_app_data found in update")
                await update.message.reply_text(
                    "❌ *Данные не получены*\nПопробуйте еще раз.",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END

            data = update.message.web_app_data.data
            logger.info(f"Raw web app data length: {len(data)}")
            logger.info(f"Raw web app data: {data}")

            booking_data = json.loads(data)
            logger.info(f"Parsed booking data keys: {booking_data.keys()}")
            logger.info(f"Parsed booking data: {booking_data}")

            # Добавляем информацию об объекте из context
            if 'selected_object' in context.user_data:
                booking_data['object_id'] = context.user_data['selected_object']
                booking_data['object_name'] = context.user_data['object_name']
                logger.info(f"Added object info from context: {context.user_data}")
            else:
                logger.warning("No selected_object found in context user_data")
                booking_data['object_id'] = 'citygate_p311'
                booking_data['object_name'] = 'CityGate P311'

            logger.info(f"Final booking data for saving: {booking_data}")

            # Сохраняем данные в CSV
            success = self.save_to_csv(booking_data)

            if success:
                logger.info("Booking successfully saved to CSV")
                await update.message.reply_text(
                    "✅ *Бронирование успешно сохранено!*\n\n"
                    f"👤 *Гость:* {booking_data.get('guest_name', '')}\n"
                    f"📅 *Даты:* {booking_data.get('check_in', '')} - {booking_data.get('check_out', '')}\n"
                    f"💰 *Сумма:* {booking_data.get('total_baht', '')} батт\n"
                    f"🏢 *Объект:* {booking_data.get('object_name', '')}",
                    parse_mode='Markdown'
                )
                logger.info(f"Booking saved for guest: {booking_data.get('guest_name', '')}")
            else:
                logger.error("Failed to save booking to CSV")
                await update.message.reply_text(
                    "❌ *Ошибка при сохранении бронирования!*\n"
                    "Попробуйте еще раз или обратитесь к администратору.",
                    parse_mode='Markdown'
                )

            return ConversationHandler.END

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Raw data that failed to parse: {data}")
            await update.message.reply_text(
                "❌ *Ошибка формата данных*\n"
                "Попробуйте еще раз или обратитесь к администратору.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error processing web app data: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ *Произошла ошибка при сохранении бронирования*\n"
                "Попробуйте еще раз или обратитесь к администратору.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    def save_to_csv(self, booking_data):
        """Сохранение данных бронирования в CSV файл"""
        logger.info("=== SAVING TO CSV ===")
        try:
            # Определяем CSV файл на основе выбранного объекта
            object_id = booking_data.get('object_id', 'citygate_p311')
            csv_file = f"{object_id}.csv"

            logger.info(f"Target CSV file: {csv_file}")
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Files in current directory: {os.listdir('.')}")

            # Проверяем существует ли файл
            file_exists = os.path.isfile(csv_file)
            logger.info(f"File exists: {file_exists}")

            # Проверяем права на запись
            if file_exists:
                try:
                    with open(csv_file, 'a') as test_file:
                        test_file.write('')
                    logger.info("File is writable")
                except Exception as e:
                    logger.error(f"File is not writable: {e}")
                    return False

            with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'Гость', 'Дата бронирования', 'Заезд', 'Выезд', 'Количество ночей',
                    'Сумма по месяцам', 'СуммаБатты', 'Аванс Батты/Рубли', 'Доплата Батты/Рубли',
                    'Источник', 'Дополнительные доплаты', 'Расходы', 'Оплата', 'Комментарий',
                    'телефон', 'дополнительный телефон', 'Рейсы', '_sync_id'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',')

                # Если файл новый, пишем заголовки
                if not file_exists:
                    logger.info("Writing headers to new CSV file")
                    writer.writeheader()

                # Генерируем уникальный sync_id
                sync_id = str(uuid.uuid4())
                logger.info(f"Generated sync_id: {sync_id}")

                # Подготавливаем данные для записи
                row_data = {
                    'Гость': booking_data.get('guest_name', ''),
                    'Дата бронирования': booking_data.get('booking_date', ''),
                    'Заезд': booking_data.get('check_in', ''),
                    'Выезд': booking_data.get('check_out', ''),
                    'Количество ночей': booking_data.get('nights_count', ''),
                    'Сумма по месяцам': booking_data.get('monthly_sum', ''),
                    'СуммаБатты': booking_data.get('total_baht', ''),
                    'Аванс Батты/Рубли': booking_data.get('advance_payment', ''),
                    'Доплата Батты/Рубли': booking_data.get('additional_payment', ''),
                    'Источник': booking_data.get('source', ''),
                    'Дополнительные доплаты': booking_data.get('extra_charges', ''),
                    'Расходы': booking_data.get('expenses', ''),
                    'Оплата': booking_data.get('payment_method', ''),
                    'Комментарий': booking_data.get('comment', ''),
                    'телефон': booking_data.get('phone', ''),
                    'дополнительный телефон': booking_data.get('additional_phone', ''),
                    'Рейсы': booking_data.get('flights', ''),
                    '_sync_id': sync_id
                }

                logger.info(f"Row data to write: {row_data}")

                writer.writerow(row_data)
                logger.info("Data successfully written to CSV")

            # Проверяем что данные записались
            if os.path.exists(csv_file):
                file_size = os.path.getsize(csv_file)
                logger.info(f"CSV file size after write: {file_size} bytes")

                # Читаем последние строки для проверки
                try:
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        logger.info(f"Total lines in CSV: {len(lines)}")
                        if lines:
                            logger.info(f"Last line in CSV: {lines[-1]}")
                except Exception as e:
                    logger.error(f"Error reading CSV for verification: {e}")

            logger.info(f"Successfully saved booking to {csv_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving to CSV: {e}", exc_info=True)
            return False

    async def cancel_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена бронирования через callback"""
        query = update.callback_query
        await query.answer()

        logger.info(f"Booking cancelled by user: {query.from_user.username}")

        await query.edit_message_text(
            "❌ *Бронирование отменено*",
            parse_mode='Markdown'
        )

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена бронирования через команду"""
        logger.info(f"Booking cancelled via command by: {update.effective_user.username}")

        await update.message.reply_text(
            "❌ *Бронирование отменено*",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    async def timeout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Таймаут сессии"""
        logger.info(f"Booking session timeout for user: {update.effective_user.username}")

        await update.message.reply_text(
            "⏰ *Время сессии истекло. Начните заново с /add_booking*",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    def get_conversation_handler(self):
        """Возвращает настроенный ConversationHandler"""
        logger.info("Setting up AddBooking conversation handler")
        return ConversationHandler(
            entry_points=[CommandHandler("add_booking", self.start_booking)],
            states={
                SELECTING_OBJECT: [
                    CallbackQueryHandler(self.select_object, pattern="^object_"),
                    CallbackQueryHandler(self.cancel_booking, pattern="^cancel_booking$")
                ],
                FILLING_FORM: [
                    MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.handle_web_app_data),
                    CallbackQueryHandler(self.cancel_booking, pattern="^cancel_booking$")
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("add_booking", self.start_booking)
            ],
            conversation_timeout=300,  # 5 минут таймаут
            name="add_booking_conversation"
        )


# Функция для регистрации обработчика в основном боте
def setup_add_booking_handler(application, bot_instance=None):
    """Регистрация обработчика добавления бронирований"""
    logger.info("Setting up add booking handler")
    booking_handler = AddBookingHandler(bot_instance)
    conv_handler = booking_handler.get_conversation_handler()
    application.add_handler(conv_handler)
    logger.info("Add booking handler setup completed")