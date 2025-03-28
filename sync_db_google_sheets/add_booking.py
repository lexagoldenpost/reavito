# add_booking.py
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from common.logging_config import setup_logger
from common.config import Config

logger = setup_logger("add_booking")

# Состояния диалога
(
    SELECT_SHEET,
    GUEST_NAME,
    BOOKING_DATE,
    CHECK_IN,
    CHECK_OUT,
    NIGHTS,
    MONTHLY_SUM,
    TOTAL_SUM,
    ADVANCE,
    ADDITIONAL_PAYMENT,
    SOURCE,
    EXTRA_CHARGES,
    EXPENSES,
    PAYMENT_METHOD,
    COMMENT,
    PHONE,
    EXTRA_PHONE,
    FLIGHTS,
    CONFIRM,
) = range(19)

# Доступные таблицы
SHEETS = {
    "HALO Title": "HALO Title",
    "Citygate Р311": "Citygate Р311",
    "Citygate B209": "Citygate B209",
    "Palmetto Karon": "Palmetto Karon",
    "Title Residence": "Title Residence",
}


class AddBookingHandler:
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = set()
        self.google_sheet_key = Config.SAMPLE_SPREADSHEET_ID
        self.credentials_json = Config.SERVICE_ACCOUNT_FILE
        logger.info("AddBookingHandler initialized")

    def get_conversation_handler(self):
        """Создает и возвращает ConversationHandler"""
        return ConversationHandler(
            entry_points=[CommandHandler("add_booking", self.start_add_booking)],
            states={
                SELECT_SHEET: [CallbackQueryHandler(self.select_sheet)],
                GUEST_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.guest_name)],
                BOOKING_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.booking_date)],
                CHECK_IN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_in)],
                CHECK_OUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_out)],
                NIGHTS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.nights)],
                MONTHLY_SUM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.monthly_sum)],
                TOTAL_SUM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.total_sum)],
                ADVANCE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.advance)],
                ADDITIONAL_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                  self.additional_payment)],
                SOURCE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.source)],
                EXTRA_CHARGES: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                             self.extra_charges)],
                EXPENSES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.expenses)],
                PAYMENT_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                              self.payment_method)],
                COMMENT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.comment)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.phone)],
                EXTRA_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.extra_phone)],
                FLIGHTS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.flights)],
                CONFIRM: [CallbackQueryHandler(self.save_data)],
            },
            fallbacks=[CommandHandler("cancel", self.handle_cancel)],
            per_message=True,
            per_chat=True,
            per_user=True
        )

    async def start_add_booking(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начало процесса бронирования"""
        try:
            user = update.effective_user
            logger.info(f"User {user.username} started add_booking")

            if not await self.bot.check_user_permission(update):
                return ConversationHandler.END

            if user.id in self.active_sessions:
                await update.message.reply_text(
                    "❌ У вас уже есть активная сессия бронирования")
                return ConversationHandler.END

            self.active_sessions.add(user.id)
            logger.debug(f"Active sessions: {self.active_sessions}")

            keyboard = [
                [InlineKeyboardButton(name, callback_data=name)]
                for name in SHEETS.values()
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "📋 Выберите таблицу для бронирования:",
                reply_markup=reply_markup
            )
            return SELECT_SHEET

        except Exception as e:
            logger.error(f"Error in start_add_booking: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
            return ConversationHandler.END

    async def select_sheet(self, update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора таблицы"""
        try:
            query = update.callback_query
            await query.answer()

            selected_sheet = query.data
            context.user_data["sheet"] = selected_sheet
            logger.info(f"Selected sheet: {selected_sheet}")

            await query.edit_message_text(
                text=f"📌 Выбрана таблица: {selected_sheet}\n\n"
                     "✏️ Введите имя гостя:"
            )
            return GUEST_NAME

        except Exception as e:
            logger.error(f"Error in select_sheet: {e}", exc_info=True)
            await query.edit_message_text("⚠️ Ошибка выбора таблицы")
            return ConversationHandler.END

    async def guest_name(self, update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка ввода имени гостя"""
        try:
            guest_name = update.message.text.strip()
            if not guest_name:
                await update.message.reply_text(
                    "❌ Имя не может быть пустым. Попробуйте снова:")
                return GUEST_NAME

            context.user_data["guest"] = guest_name
            logger.info(f"Guest name set: {guest_name}")

            await update.message.reply_text(
                "📅 Введите дату бронирования (ДД.ММ.ГГГГ):")
            return BOOKING_DATE

        except Exception as e:
            logger.error(f"Error in guest_name: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки имени")
            return ConversationHandler.END

    async def booking_date(self, update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка даты бронирования"""
        try:
            date_str = update.message.text.strip()
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            formatted_date = date.strftime("%Y-%m-%d 00:00:00")
            context.user_data["booking_date"] = formatted_date
            logger.info(f"Booking date set: {formatted_date}")

            await update.message.reply_text("🏨 Введите дату заезда (ДД.ММ.ГГГГ):")
            return CHECK_IN

        except ValueError:
            logger.warning(f"Invalid date format: {update.message.text}")
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return BOOKING_DATE
        except Exception as e:
            logger.error(f"Error in booking_date: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки даты")
            return ConversationHandler.END

    async def check_in(self, update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка даты заезда"""
        try:
            date_str = update.message.text.strip()
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            formatted_date = date.strftime("%Y-%m-%d 00:00:00")
            context.user_data["check_in"] = formatted_date
            logger.info(f"Check-in date set: {formatted_date}")

            await update.message.reply_text("🚪 Введите дату выезда (ДД.ММ.ГГГГ):")
            return CHECK_OUT

        except ValueError:
            logger.warning(f"Invalid date format: {update.message.text}")
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return CHECK_IN
        except Exception as e:
            logger.error(f"Error in check_in: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки даты заезда")
            return ConversationHandler.END

    async def check_out(self, update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка даты выезда"""
        try:
            date_str = update.message.text.strip()
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            formatted_date = date.strftime("%Y-%m-%d 00:00:00")
            context.user_data["check_out"] = formatted_date
            logger.info(f"Check-out date set: {formatted_date}")

            await update.message.reply_text("🌙 Введите количество ночей:")
            return NIGHTS

        except ValueError:
            logger.warning(f"Invalid date format: {update.message.text}")
            await update.message.reply_text(
                "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return CHECK_OUT
        except Exception as e:
            logger.error(f"Error in check_out: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки даты выезда")
            return ConversationHandler.END

    async def nights(self, update: Update,
                   context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка количества ночей"""
        try:
            nights = update.message.text.strip()
            if not nights:
                await update.message.reply_text("❌ Введите количество ночей:")
                return NIGHTS

            context.user_data["nights"] = nights
            logger.info(f"Nights set: {nights}")

            await update.message.reply_text(
                "💰 Введите сумму по месяцам (например: 'Окт 15000 Ноя 20000'):")
            return MONTHLY_SUM

        except Exception as e:
            logger.error(f"Error in nights: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки количества ночей")
            return ConversationHandler.END

    async def monthly_sum(self, update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка суммы по месяцам"""
        try:
            monthly_sum = update.message.text.strip()
            if not monthly_sum:
                await update.message.reply_text("❌ Введите сумму по месяцам:")
                return MONTHLY_SUM

            context.user_data["monthly_sum"] = monthly_sum
            logger.info(f"Monthly sum set: {monthly_sum}")

            await update.message.reply_text("💵 Введите общую сумму бронирования:")
            return TOTAL_SUM

        except Exception as e:
            logger.error(f"Error in monthly_sum: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки суммы по месяцам")
            return ConversationHandler.END

    async def total_sum(self, update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка общей суммы"""
        try:
            total_sum = update.message.text.strip()
            if not total_sum:
                await update.message.reply_text("❌ Введите общую сумму:")
                return TOTAL_SUM

            context.user_data["total_sum"] = total_sum
            logger.info(f"Total sum set: {total_sum}")

            await update.message.reply_text(
                "💳 Введите сумму аванса (в баттах/рублях):")
            return ADVANCE

        except Exception as e:
            logger.error(f"Error in total_sum: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки общей суммы")
            return ConversationHandler.END

    async def advance(self, update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка аванса"""
        try:
            advance = update.message.text.strip()
            if not advance:
                await update.message.reply_text("❌ Введите сумму аванса:")
                return ADVANCE

            context.user_data["advance"] = advance
            logger.info(f"Advance set: {advance}")

            await update.message.reply_text("💴 Введите сумму доплаты (если есть):")
            return ADDITIONAL_PAYMENT

        except Exception as e:
            logger.error(f"Error in advance: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки аванса")
            return ConversationHandler.END

    async def additional_payment(self, update: Update,
                               context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка доплаты"""
        try:
            additional_payment = update.message.text.strip()
            context.user_data["additional_payment"] = additional_payment
            logger.info(f"Additional payment set: {additional_payment}")

            await update.message.reply_text(
                "📌 Введите источник бронирования (Авито, Booking и т.д.):")
            return SOURCE

        except Exception as e:
            logger.error(f"Error in additional_payment: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки доплаты")
            return ConversationHandler.END

    async def source(self, update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка источника бронирования"""
        try:
            source = update.message.text.strip()
            if not source:
                await update.message.reply_text("❌ Введите источник бронирования:")
                return SOURCE

            context.user_data["source"] = source
            logger.info(f"Source set: {source}")

            await update.message.reply_text(
                "💸 Введите дополнительные платежи (если есть):")
            return EXTRA_CHARGES

        except Exception as e:
            logger.error(f"Error in source: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки источника")
            return ConversationHandler.END

    async def extra_charges(self, update: Update,
                          context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка дополнительных платежей"""
        try:
            extra_charges = update.message.text.strip()
            context.user_data["extra_charges"] = extra_charges
            logger.info(f"Extra charges set: {extra_charges}")

            await update.message.reply_text("🧹 Введите расходы (уборка и т.д.):")
            return EXPENSES

        except Exception as e:
            logger.error(f"Error in extra_charges: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки доп. платежей")
            return ConversationHandler.END

    async def expenses(self, update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка расходов"""
        try:
            expenses = update.message.text.strip()
            context.user_data["expenses"] = expenses
            logger.info(f"Expenses set: {expenses}")

            await update.message.reply_text("💳 Введите способ оплаты:")
            return PAYMENT_METHOD

        except Exception as e:
            logger.error(f"Error in expenses: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки расходов")
            return ConversationHandler.END

    async def payment_method(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка способа оплаты"""
        try:
            payment_method = update.message.text.strip()
            if not payment_method:
                await update.message.reply_text("❌ Введите способ оплаты:")
                return PAYMENT_METHOD

            context.user_data["payment_method"] = payment_method
            logger.info(f"Payment method set: {payment_method}")

            await update.message.reply_text("📝 Введите комментарий (если есть):")
            return COMMENT

        except Exception as e:
            logger.error(f"Error in payment_method: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки способа оплаты")
            return ConversationHandler.END

    async def comment(self, update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка комментария"""
        try:
            comment = update.message.text.strip()
            context.user_data["comment"] = comment
            logger.info(f"Comment set: {comment}")

            await update.message.reply_text("📱 Введите контактный телефон:")
            return PHONE

        except Exception as e:
            logger.error(f"Error in comment: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки комментария")
            return ConversationHandler.END

    async def phone(self, update: Update,
                  context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка телефона"""
        try:
            phone = update.message.text.strip()
            if not phone:
                await update.message.reply_text("❌ Введите телефон:")
                return PHONE

            context.user_data["phone"] = phone
            logger.info(f"Phone set: {phone}")

            await update.message.reply_text(
                "📱 Введите дополнительный телефон (если есть):")
            return EXTRA_PHONE

        except Exception as e:
            logger.error(f"Error in phone: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки телефона")
            return ConversationHandler.END

    async def extra_phone(self, update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка дополнительного телефона"""
        try:
            extra_phone = update.message.text.strip()
            context.user_data["extra_phone"] = extra_phone
            logger.info(f"Extra phone set: {extra_phone}")

            await update.message.reply_text(
                "✈️ Введите информацию о рейсах (если есть):")
            return FLIGHTS

        except Exception as e:
            logger.error(f"Error in extra_phone: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки доп. телефона")
            return ConversationHandler.END

    async def flights(self, update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка информации о рейсах"""
        try:
            flights = update.message.text.strip()
            context.user_data["flights"] = flights
            logger.info(f"Flights info set: {flights}")

            # Формируем сводку данных
            summary = self._generate_summary(context.user_data)
            keyboard = [
                [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")],
                [InlineKeyboardButton("❌ Отменить", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"📋 Проверьте данные:\n\n{summary}\n\nПодтверждаете?",
                reply_markup=reply_markup
            )
            return CONFIRM

        except Exception as e:
            logger.error(f"Error in flights: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки информации о рейсах")
            return ConversationHandler.END

    async def save_data(self, update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> int:
        """Сохранение данных в Google Sheets"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        if query.data == "cancel":
            self.active_sessions.discard(user_id)
            context.user_data.clear()
            await query.edit_message_text("❌ Бронирование отменено")
            return ConversationHandler.END

        try:
            # Подключение к Google Sheets
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                self.credentials_json, scope
            )
            client = gspread.authorize(creds)
            sheet = client.open_by_key(self.google_sheet_key).worksheet(
                context.user_data["sheet"])

            # Подготовка данных для сохранения
            row_data = [
                context.user_data.get("guest", ""),
                context.user_data.get("booking_date", ""),
                context.user_data.get("check_in", ""),
                context.user_data.get("check_out", ""),
                context.user_data.get("nights", ""),
                context.user_data.get("monthly_sum", ""),
                context.user_data.get("total_sum", ""),
                context.user_data.get("advance", ""),
                context.user_data.get("additional_payment", ""),
                context.user_data.get("source", ""),
                context.user_data.get("extra_charges", ""),
                context.user_data.get("expenses", ""),
                context.user_data.get("payment_method", ""),
                context.user_data.get("comment", ""),
                context.user_data.get("phone", ""),
                context.user_data.get("extra_phone", ""),
                context.user_data.get("flights", ""),
            ]

            # Добавление новой строки
            sheet.append_row(row_data)
            logger.info("Data successfully saved to Google Sheets")

            # Очистка
            self.active_sessions.discard(user_id)
            context.user_data.clear()

            await query.edit_message_text(
                "✅ Бронирование успешно сохранено!\n"
                "Для нового бронирования используйте /add_booking"
            )
            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error saving data: {e}", exc_info=True)
            self.active_sessions.discard(user_id)
            await query.edit_message_text(
                "❌ Ошибка при сохранении данных. Попробуйте позже."
            )
            return ConversationHandler.END

    async def handle_cancel(self, update: Update,
                          context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка команды отмены"""
        user_id = update.effective_user.id
        self.active_sessions.discard(user_id)
        context.user_data.clear()
        logger.info(f"Booking canceled by user {user_id}")

        await update.message.reply_text(
            "❌ Текущее бронирование отменено.\n"
            "Для нового бронирования используйте /add_booking"
        )
        return ConversationHandler.END

    def _generate_summary(self, data):
        """Генерация сводки данных"""
        return (
            f"Таблица: {data.get('sheet', '')}\n"
            f"Гость: {data.get('guest', '')}\n"
            f"Дата бронирования: {data.get('booking_date', '')}\n"
            f"Заезд: {data.get('check_in', '')}\n"
            f"Выезд: {data.get('check_out', '')}\n"
            f"Ночей: {data.get('nights', '')}\n"
            f"Сумма по месяцам: {data.get('monthly_sum', '')}\n"
            f"Общая сумма: {data.get('total_sum', '')}\n"
            f"Аванс: {data.get('advance', '')}\n"
            f"Доплата: {data.get('additional_payment', '')}\n"
            f"Источник: {data.get('source', '')}\n"
            f"Доп. платежи: {data.get('extra_charges', '')}\n"
            f"Расходы: {data.get('expenses', '')}\n"
            f"Способ оплаты: {data.get('payment_method', '')}\n"
            f"Комментарий: {data.get('comment', '')}\n"
            f"Телефон: {data.get('phone', '')}\n"
            f"Доп. телефон: {data.get('extra_phone', '')}\n"
            f"Рейсы: {data.get('flights', '')}"
        )

