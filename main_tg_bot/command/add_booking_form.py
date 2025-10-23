# add_booking_form.py
import csv
import json
import os
import uuid
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from booking_objects import get_booking_sheet
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        self.bot = bot_instance
        # URL удаленного веб-сервера с формой бронирования
        self.remote_web_app_url = Config.REMOTE_WEB_APP_URL + Config.REMOTE_WEB_APP_CREATE_BOOKING_URL

        # Получаем объекты из booking_objects
        self.objects = self._load_objects_from_booking_sheets()

    def _load_objects_from_booking_sheets(self):
        """Загружает объекты из booking_objects"""
        objects = {}
        # Эти объекты должны соответствовать тем, что определены в booking_objects.py
        object_mapping = {
            'citygate_p311': 'CityGate P311',
            'citygate_b209': 'CityGate B209',
            'halo_title': 'Halo Title',
            'palmetto_karon': 'Palmetto Karon',
            'title_residence': 'Title Residence',
            'halo_ju701_двушка': 'Halo JU701 Двушка'
        }

        # Проверяем какие объекты действительно доступны
        for object_id, object_name in object_mapping.items():
            sheet = get_booking_sheet(object_name)
            if sheet:
                objects[object_id] = object_name
                logger.info(f"Loaded object: {object_id} -> {object_name}")

        return objects

    async def start_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса бронирования"""
        logger.info("=== START BOOKING PROCESS ===")
        logger.info(f"User: {update.effective_user.username} (ID: {update.effective_user.id})")

        # Проверка прав доступа через экземпляр бота, если он передан
        if self.bot and not await self.bot.check_user_permission(update):
            logger.warning("User permission denied")
            return ConversationHandler.END

        # Создаем клавиатуру с доступными объектами
        keyboard = []
        for object_id, object_name in self.objects.items():
            keyboard.append([InlineKeyboardButton(f"🏢 {object_name}", callback_data=f"object_{object_id}")])

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

            # Формируем URL с параметрами для Mini App
            web_app_url = self._build_web_app_url(object_id, query.from_user.id)
            logger.info(f"Generated Mini App URL: {web_app_url}")

            # Используем обычную кнопку с URL для открытия в Telegram Mini App
            keyboard = [
                [InlineKeyboardButton(
                    "📝 Заполнить форму бронирования",
                    url=web_app_url  # Открывается в Mini App внутри Telegram
                )],
                [InlineKeyboardButton("🔄 Проверить сохраненные данные", callback_data="check_saved_data")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"🏢 *Выбран объект:* {self.objects[object_id]}\n\n"
                "📝 *Для создания бронирования нажмите кнопку ниже:*\n\n"
                "_Форма откроется в Telegram Mini App_\n\n"
                "После заполнения формы она автоматически закроется и данные поступят в бота.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

            logger.info("Mini App button presented to user")
            return FILLING_FORM

        except Exception as e:
            logger.error(f"Error creating Mini App URL: {str(e)}")
            await query.edit_message_text(
                "❌ *Ошибка при создании формы бронирования*\n\n"
                "Пожалуйста, попробуйте позже или обратитесь к администратору.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    def _build_web_app_url(self, object_id: str, user_id: int) -> str:
        """Строит URL для открытия в Telegram Mini App"""

        base_url = self.remote_web_app_url  # например: "https://ci84606-wordpress-rdeld.tw1.ru/?page_id=8"

        # Разбираем URL
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        # Добавляем параметры для Mini App
        query_params['object'] = object_id
        query_params['user_id'] = str(user_id)
        query_params['tgWebApp'] = '1'  # Флаг что открыто в Telegram

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
        """Обработка данных из Mini App"""
        logger.info(">>> handle_web_app_data CALLED")

        try:
            web_app_data = update.message.web_app_data
            data = json.loads(web_app_data.data)
            logger.info(f"Mini App data received: {json.dumps(data, indent=2, ensure_ascii=False)}")

            # Проверяем успешное сохранение в JSON
            json_save_success = data.get('json_save_success', False)

            if json_save_success:
                logger.info("✅ Booking successfully saved to JSON file on remote server")
                logger.info(f"JSON save message: {data.get('json_save_message', 'No message')}")
                logger.info(f"Booking ID: {data.get('booking_id', 'No ID')}")

                # Сохраняем данные в локальный CSV
                success = await self.save_booking_to_local_storage(data, context)

                if success:
                    logger.info("✅ Data successfully saved to local storage")
                    await update.message.reply_text(
                        "✅ *Бронирование успешно сохранено!*\n\n"
                        f"🏢 *Объект:* {data.get('object_id', 'Не указано')}\n"
                        f"👤 *Гость:* {data.get('guest_name', 'Не указано')}\n"
                        f"📅 *Заезд:* {data.get('check_in', 'Не указано')}\n"
                        f"📅 *Выезд:* {data.get('check_out', 'Не указано')}\n"
                        f"🌙 *Ночей:* {data.get('nights_count', 'Не указано')}\n"
                        f"💰 *Сумма:* {data.get('total_baht', '0')} батт",
                        parse_mode='Markdown'
                    )
                else:
                    logger.error("Failed to save booking to local storage")
                    await update.message.reply_text(
                        "❌ *Ошибка при сохранении в локальную базу*\n\n"
                        "Данные сохранены на сервере, но возникла локальная ошибка.",
                        parse_mode='Markdown'
                    )
            else:
                # Пытаемся сохранить напрямую в локальное хранилище
                success = await self.save_booking_to_local_storage(data, context)
                if success:
                    logger.info("Booking saved directly to local storage")
                    await update.message.reply_text(
                        "✅ *Бронирование сохранено в локальную систему!*",
                        parse_mode='Markdown'
                    )
                else:
                    logger.error("Failed to save booking")
                    await update.message.reply_text(
                        "❌ *Ошибка при сохранении бронирования*",
                        parse_mode='Markdown'
                    )

            # Отправляем уведомление администратору
            await self._send_admin_notification(data, context)

        except Exception as e:
            logger.error(f"Error processing Mini App data: {str(e)}")
            await update.message.reply_text(
                "❌ *Ошибка при обработке данных*\n\n"
                "Пожалуйста, попробуйте еще раз.",
                parse_mode='Markdown'
            )

        return ConversationHandler.END

    async def save_booking_to_local_storage(self, booking_data: dict, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Сохраняет бронирование в локальное хранилище (CSV)"""
        try:
            object_id = booking_data.get('object_id')
            if not object_id:
                logger.error("No object_id in booking data")
                return False

            # Получаем соответствующий CSV файл из booking_objects
            object_name = self.objects.get(object_id)
            if not object_name:
                logger.error(f"Object name not found for ID: {object_id}")
                return False

            booking_sheet = get_booking_sheet(object_name)
            if not booking_sheet:
                logger.error(f"Booking sheet not found for: {object_name}")
                return False

            csv_file = booking_sheet.filepath
            logger.info(f"Saving to CSV file: {csv_file}")

            # Проверяем существование файла и создаем заголовки если нужно
            file_exists = os.path.isfile(csv_file)

            with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'Гость', 'Дата бронирования', 'Заезд', 'Выезд', 'Количество ночей',
                    'СуммаБатты', 'Аванс Батты/Рубли', 'Доплата Батты/Рубли', 'Источник',
                    'Дополнительные доплаты', 'Расходы', 'Оплата', 'Комментарий', 'телефон',
                    'дополнительный телефон', 'Рейсы', '_sync_id'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if not file_exists:
                    writer.writeheader()
                    logger.info("CSV file created with headers")

                # Подготавливаем данные для записи в формате исходного CSV
                row_data = {
                    'Гость': booking_data.get('guest_name', ''),
                    'Дата бронирования': booking_data.get('booking_date', ''),
                    'Заезд': booking_data.get('check_in', ''),
                    'Выезд': booking_data.get('check_out', ''),
                    'Количество ночей': booking_data.get('nights_count', ''),
                    'СуммаБатты': booking_data.get('total_baht', ''),
                    'Аванс Батты/Рубли': booking_data.get('advance_payment', ''),
                    'Доплата Батты/Рубли': booking_data.get('additional_payment', ''),
                    'Источник': booking_data.get('source', ''),
                    'Дополнительные доплаты': '',
                    'Расходы': '',
                    'Оплата': booking_data.get('payment_method', ''),
                    'Комментарий': booking_data.get('comment', ''),
                    'телефон': booking_data.get('phone', ''),
                    'дополнительный телефон': booking_data.get('additional_phone', ''),
                    'Рейсы': booking_data.get('flights', ''),
                    '_sync_id': booking_data.get('sync_id', booking_data.get('id', str(uuid.uuid4())))
                }

                writer.writerow(row_data)
                logger.info(f"✅ Booking successfully saved to CSV: {csv_file}")

                # Логируем успешное сохранение
                logger.info("=== BOOKING SUCCESSFULLY SAVED ===")
                logger.info(f"Object: {object_name}")
                logger.info(f"Guest: {booking_data.get('guest_name')}")
                logger.info(f"Check-in: {booking_data.get('check_in')}")
                logger.info(f"Check-out: {booking_data.get('check_out')}")
                logger.info(f"Total: {booking_data.get('total_baht')} baht")

                return True

        except Exception as e:
            logger.error(f"Error saving booking to local storage: {str(e)}")
            return False

    async def check_saved_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка сохраненных данных"""
        query = update.callback_query
        await query.answer()

        try:
            object_id = context.user_data.get('selected_object')
            if not object_id:
                await query.edit_message_text("❌ Объект не выбран")
                return FILLING_FORM

            object_name = self.objects.get(object_id)
            booking_sheet = get_booking_sheet(object_name)

            if booking_sheet and booking_sheet.exists():
                # Читаем последние записи из CSV
                import pandas as pd
                df = booking_sheet.load()
                if not df.empty:
                    last_bookings = df.tail(3)  # Последние 3 бронирования

                    message = f"📊 *Последние бронирования для {object_name}:*\n\n"
                    for _, booking in last_bookings.iterrows():
                        message += f"👤 {booking.get('Гость', 'N/A')}\n"
                        message += f"📅 {booking.get('Заезд', 'N/A')} - {booking.get('Выезд', 'N/A')}\n"
                        message += f"💰 {booking.get('СуммаБатты', 'N/A')} батт\n"
                        message += "─" * 20 + "\n"

                    await query.edit_message_text(message, parse_mode='Markdown')
                else:
                    await query.edit_message_text("📭 Нет сохраненных бронирований")
            else:
                await query.edit_message_text("📭 Файл с бронированиями не найден")

        except Exception as e:
            logger.error(f"Error checking saved data: {str(e)}")
            await query.edit_message_text("❌ Ошибка при проверке данных")

        return FILLING_FORM

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
        message = "🏨 <b>НОВОЕ БРОНИРОВАНИЕ ИЗ MINI APP</b> 🏨\n\n"
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

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена процесса бронирования"""
        logger.info("Booking process cancelled by user")
        await update.message.reply_text(
            "❌ *Процесс бронирования отменен*",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    async def timeout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Таймаут процесса бронирования"""
        logger.info("Booking process timeout")
        await update.message.reply_text(
            "⏰ *Время сессии истекло*\n\n"
            "Используйте /add_booking чтобы начать заново.",
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
                    MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.handle_web_app_data),
                    CallbackQueryHandler(self.check_saved_data, pattern='^check_saved_data$')
                ]
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel),
                CommandHandler('add_booking', self.start_booking)
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