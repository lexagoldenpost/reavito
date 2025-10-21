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

    async def start_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса бронирования"""
        # Проверка прав доступа через экземпляр бота, если он передан
        if self.bot and not await self.bot.check_user_permission(update):
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

        return SELECTING_OBJECT

    async def select_object(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора объекта"""
        query = update.callback_query
        await query.answer()

        # Проверка прав доступа
        if self.bot and not await self.bot.check_user_permission(update):
            return ConversationHandler.END

        # Извлекаем object_id из callback_data, убирая префикс "object_"
        callback_data = query.data
        object_id = callback_data.replace("object_", "")

        if object_id not in self.objects:
            await query.edit_message_text(
                "❌ *Ошибка: объект не найден*",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        context.user_data['selected_object'] = object_id
        context.user_data['object_name'] = self.objects.get(object_id, "Unknown Object")

        # Получаем URL через экземпляр бота
        try:
            if self.bot:
                base_url = self.bot.get_web_app_url()
            else:
                # Fallback: пытаемся получить URL самостоятельно
                from main_tg_bot.web_app_server import get_web_app_url
                base_url = get_web_app_url()

            if not base_url:
                raise Exception("Web app URL not available")

        except Exception as e:
            logger.error(f"Failed to get web app URL: {e}")
            await query.edit_message_text(
                "❌ *Веб-сервер временно недоступен*\nПопробуйте позже.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        web_app_url = f"{base_url}/booking-form?object={object_id}&user_id={query.from_user.id}"
        web_app_info = WebAppInfo(url=web_app_url)

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
            "Теперь заполните форму бронирования:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        return FILLING_FORM

    async def handle_web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка данных из Web App"""
        try:
            # Проверка прав доступа
            if self.bot and not await self.bot.check_user_permission(update):
                return ConversationHandler.END

            data = update.message.web_app_data.data
            booking_data = json.loads(data)

            # Добавляем информацию об объекте из context
            if 'selected_object' in context.user_data:
                booking_data['object_id'] = context.user_data['selected_object']
                booking_data['object_name'] = context.user_data['object_name']

            # Сохраняем данные в CSV
            success = self.save_to_csv(booking_data)

            if success:
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
                await update.message.reply_text(
                    "❌ *Ошибка при сохранении бронирования!*\n"
                    "Попробуйте еще раз или обратитесь к администратору.",
                    parse_mode='Markdown'
                )

            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error processing web app data: {e}")
            await update.message.reply_text(
                "❌ *Произошла ошибка при сохранении бронирования*\n"
                "Попробуйте еще раз или обратитесь к администратору.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

    def save_to_csv(self, booking_data):
        """Сохранение данных бронирования в CSV файл"""
        try:
            # Проверяем существует ли файл
            file_exists = os.path.isfile(self.csv_file)

            with open(self.csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'Гость', 'Дата бронирования', 'Заезд', 'Выезд', 'Количество ночей',
                    'Сумма по месяцам', 'СуммаБатты', 'Аванс Батты/Рубли', 'Доплата Батты/Рубли',
                    'Источник', 'Дополнительные доплаты', 'Расходы', 'Оплата', 'Комментарий',
                    'телефон', 'дополнительный телефон', 'Рейсы', '_sync_id', 'ID'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',')

                # Если файл новый, пишем заголовки
                if not file_exists:
                    writer.writeheader()

                # Генерируем уникальные ID
                sync_id = str(uuid.uuid4())
                record_id = self.get_next_id()

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
                    '_sync_id': sync_id,
                    'ID': record_id
                }

                writer.writerow(row_data)

            return True

        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            return False

    def get_next_id(self):
        """Получение следующего ID для записи"""
        try:
            if not os.path.isfile(self.csv_file):
                return 1

            with open(self.csv_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                if not rows:
                    return 1

                # Находим максимальный ID
                max_id = 0
                for row in rows:
                    try:
                        row_id = int(row.get('ID', 0))
                        if row_id > max_id:
                            max_id = row_id
                    except (ValueError, TypeError):
                        continue

                return max_id + 1

        except Exception as e:
            logger.error(f"Error getting next ID: {e}")
            return 1

    async def cancel_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена бронирования через callback"""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "❌ *Бронирование отменено*",
            parse_mode='Markdown'
        )

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена бронирования через команду"""
        await update.message.reply_text(
            "❌ *Бронирование отменено*",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    async def timeout(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Таймаут сессии"""
        await update.message.reply_text(
            "⏰ *Время сессии истекло. Начните заново с /add_booking*",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    def get_conversation_handler(self):
        """Возвращает настроенный ConversationHandler"""
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
    booking_handler = AddBookingHandler(bot_instance)
    conv_handler = booking_handler.get_conversation_handler()
    application.add_handler(conv_handler)
    logger.info("Add booking handler setup completed")