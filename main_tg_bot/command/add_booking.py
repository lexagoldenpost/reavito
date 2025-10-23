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

            # Формируем URL с параметрами для веб-формы
            web_app_url = self._build_web_app_url(object_id, query.from_user.id)
            logger.info(f"Generated WebApp URL: {web_app_url}")

            keyboard = [
                [InlineKeyboardButton(
                    "📝 Заполнить форму бронирования",
                    web_app=WebAppInfo(url=web_app_url)
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"🏢 *Выбран объект:* {self.objects[object_id]}\n\n"
                "📝 *Для создания бронирования нажмите кнопку ниже:*\n\n"
                "_Форма откроется в Telegram WebApp_",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

            logger.info("WebApp button presented to user")
            return FILLING_FORM

        except Exception as e:
            logger.error(f"Error creating WebApp URL: {str(e)}")
            await query.edit_message_text(
                "❌ *Ошибка при создании формы бронирования*\n\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    def _build_web_app_url(self, object_id: str, user_id: int) -> str:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        base_url = self.remote_web_app_url  # например: "https://ci84606-wordpress-rdeld.tw1.ru/?page_id=8"

        # Разбираем URL
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        # Добавляем новые параметры
        query_params['object'] = object_id
        query_params['user_id'] = str(user_id)

        # Собираем обратно
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

        return new_url

    async def handle_web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(">>> handle_web_app_data CALLED")
        logger.info(f"Update type: {update}")
        if update.message and update.message.web_app_data:
            logger.info(f"Raw WebApp data: {update.message.web_app_data.data}")
        else:
            logger.warning("No web_app_data in message!")
            return ConversationHandler.END

        logger.info("=== WEB APP DATA RECEIVED ===")
        """Обработка данных из WebApp - вызывается когда форма отправляет данные через sendData()"""
        logger.info("=== WEB APP DATA RECEIVED ===")

        try:
            web_app_data = update.message.web_app_data
            data = json.loads(web_app_data.data)
            logger.info(f"WebApp data received: {json.dumps(data, indent=2, ensure_ascii=False)}")

            # Сохраняем бронирование в CSV
            success = self.save_booking_to_csv(data)

            if success:
                logger.info("Booking successfully saved to CSV")
                await update.message.reply_text(
                    "✅ *Бронирование успешно сохранено!*\n\n"
                    "Все данные записаны в систему.",
                    parse_mode='Markdown'
                )

                # Отправляем уведомление администратору
                await self._send_admin_notification(data, context)

            else:
                logger.error("Failed to save booking to CSV")
                await update.message.reply_text(
                    "❌ *Ошибка при сохранении бронирования*\n\n"
                    "Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"Error processing WebApp data: {str(e)}")
            await update.message.reply_text(
                "❌ *Ошибка при обработке данных*\n\n"
                "Пожалуйста, попробуйте еще раз.",
                parse_mode='Markdown'
            )

        return ConversationHandler.END

    async def _send_admin_notification(self, booking_data: dict, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет уведомление администратору о новом бронировании"""
        try:
            message = self._format_booking_notification(booking_data)
            await context.bot.send_message(
                chat_id=Config.ADMIN_CHAT_ID,
                text=message,
                parse_mode='HTML'
            )
            logger.info("Admin notification sent")
        except Exception as e:
            logger.error(f"Error sending admin notification: {str(e)}")

    def _format_booking_notification(self, booking_data: dict) -> str:
        """Форматирует уведомление о бронировании"""
        message = "🏨 <b>НОВОЕ БРОНИРОВАНИЕ ИЗ WEB-FORM</b> 🏨\n\n"
        message += f"<b>👤 Гость:</b> {booking_data.get('guest_name', 'Не указано')}\n"
        message += f"<b>📞 Телефон:</b> {booking_data.get('phone', 'Не указан')}\n"

        if booking_data.get('additional_phone'):
            message += f"<b>📞 Доп. телефон:</b> {booking_data['additional_phone']}\n"

        message += f"<b>📅 Заезд:</b> {booking_data.get('check_in', 'Не указано')}\n"
        message += f"<b>📅 Выезд:</b> {booking_data.get('check_out', 'Не указано')}\n"
        message += f"<b>🌙 Ночей:</b> {booking_data.get('nights_count', 'Не указано')}\n"

        if booking_data.get('total_baht'):
            message += f"<b>💰 Сумма:</b> {booking_data['total_baht']} батт\n"

        if booking_data.get('advance_payment') and booking_data['advance_payment'] != '0/0':
            message += f"<b>💳 Аванс:</b> {booking_data['advance_payment']}\n"

        if booking_data.get('additional_payment') and booking_data['additional_payment'] != '0/0':
            message += f"<b>💳 Доплата:</b> {booking_data['additional_payment']}\n"

        if booking_data.get('source'):
            message += f"<b>📊 Источник:</b> {booking_data['source']}\n"

        if booking_data.get('flights'):
            message += f"<b>✈️ Рейсы:</b> {booking_data['flights']}\n"

        if booking_data.get('payment_method'):
            message += f"<b>💸 Способ оплаты:</b> {booking_data['payment_method']}\n"

        if booking_data.get('comment'):
            message += f"<b>📝 Комментарий:</b> {booking_data['comment']}\n"

        message += f"\n<b>🏢 Объект:</b> {booking_data.get('object_id', 'Не указан')}\n"
        message += f"<b>👤 Менеджер ID:</b> {booking_data.get('user_id', 'Не указан')}\n"
        message += f"<b>📅 Дата создания:</b> {booking_data.get('booking_date', 'Не указана')}"

        return message

    def save_booking_to_csv(self, booking_data: dict) -> bool:
        """Сохраняет данные бронирования в CSV файл"""
        try:
            logger.info("=== SAVING BOOKING TO CSV ===")
            logger.info(f"Booking data: {json.dumps(booking_data, indent=2, ensure_ascii=False)}")

            # Проверяем существование файла и создаем заголовки если нужно
            file_exists = os.path.isfile(self.csv_file)

            with open(self.csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'id', 'guest_name', 'phone', 'additional_phone', 'check_in',
                    'check_out', 'nights_count', 'total_baht', 'advance_payment',
                    'additional_payment', 'source', 'flights', 'payment_method',
                    'comment', 'booking_date', 'object_id', 'user_id', 'created_at'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if not file_exists:
                    writer.writeheader()
                    logger.info("CSV file created with headers")

                # Подготавливаем данные для записи
                row_data = {
                    'id': str(uuid.uuid4()),
                    'guest_name': booking_data.get('guest_name', ''),
                    'phone': booking_data.get('phone', ''),
                    'additional_phone': booking_data.get('additional_phone', ''),
                    'check_in': booking_data.get('check_in', ''),
                    'check_out': booking_data.get('check_out', ''),
                    'nights_count': booking_data.get('nights_count', ''),
                    'total_baht': booking_data.get('total_baht', ''),
                    'advance_payment': booking_data.get('advance_payment', ''),
                    'additional_payment': booking_data.get('additional_payment', ''),
                    'source': booking_data.get('source', ''),
                    'flights': booking_data.get('flights', ''),
                    'payment_method': booking_data.get('payment_method', ''),
                    'comment': booking_data.get('comment', ''),
                    'booking_date': booking_data.get('booking_date', ''),
                    'object_id': booking_data.get('object_id', ''),
                    'user_id': booking_data.get('user_id', ''),
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                writer.writerow(row_data)
                logger.info(f"Booking successfully saved to CSV: {self.csv_file}")
                logger.info(f"Row data: {row_data}")

                return True

        except Exception as e:
            logger.error(f"Error saving booking to CSV: {str(e)}")
            return False

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена процесса бронирования"""
        logger.info("Booking process cancelled by user")
        await update.message.reply_text(
            "❌ *Процесс бронирования отменен*",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    def get_conversation_handler(self):
        """Возвращает ConversationHandler для добавления бронирований"""
        return ConversationHandler(
            entry_points=[CommandHandler('add_booking', self.start_booking)],
            states={
                SELECTING_OBJECT: [
                    CallbackQueryHandler(self.select_object, pattern='^object_')
                ],
                FILLING_FORM: [
                    MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.handle_web_app_data)
                ]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
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