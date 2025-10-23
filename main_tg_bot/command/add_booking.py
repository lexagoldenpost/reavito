import uuid
from datetime import datetime

import pandas as pd
from main_tg_bot.booking_objects import BOOKING_SHEETS, get_booking_sheet
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


class AddBookingHandler:
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = set()

    def get_conversation_handler(self):
        """Создает и возвращает ConversationHandler"""
        return ConversationHandler(
            entry_points=[CommandHandler("add_booking", self.start_add_booking)],
            states={
                SELECT_SHEET: [CallbackQueryHandler(self.select_sheet)],
                GUEST_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.guest_name)
                ],
                BOOKING_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.booking_date)
                ],
                CHECK_IN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_in)
                ],
                CHECK_OUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_out)
                ],
                NIGHTS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.nights),
                    CallbackQueryHandler(self.skip_nights, pattern="^skip_nights$"),
                ],
                MONTHLY_SUM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.monthly_sum),
                    CallbackQueryHandler(
                        self.skip_monthly_sum, pattern="^skip_monthly_sum$"
                    ),
                ],
                TOTAL_SUM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.total_sum)
                ],
                ADVANCE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.advance)
                ],
                ADDITIONAL_PAYMENT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.additional_payment
                    ),
                    CallbackQueryHandler(
                        self.skip_additional_payment,
                        pattern="^skip_additional_payment$",
                    ),
                ],
                SOURCE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.source)
                ],
                EXTRA_CHARGES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.extra_charges),
                    CallbackQueryHandler(
                        self.skip_extra_charges, pattern="^skip_extra_charges$"
                    ),
                ],
                EXPENSES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.expenses),
                    CallbackQueryHandler(self.skip_expenses, pattern="^skip_expenses$"),
                ],
                PAYMENT_METHOD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.payment_method)
                ],
                COMMENT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.comment),
                    CallbackQueryHandler(self.skip_comment, pattern="^skip_comment$"),
                ],
                PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.phone)
                ],
                EXTRA_PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.extra_phone),
                    CallbackQueryHandler(
                        self.skip_extra_phone, pattern="^skip_extra_phone$"
                    ),
                ],
                FLIGHTS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.flights),
                    CallbackQueryHandler(self.skip_flights, pattern="^skip_flights$"),
                ],
                CONFIRM: [CallbackQueryHandler(self.confirm_booking)],
            },
            fallbacks=[CommandHandler("cancel", self.handle_cancel)],
            conversation_timeout=300,  # 5 минут таймаут для неактивных сессий
        )

    async def cleanup_session(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Очищает данные сессии"""
        if user_id in self.active_sessions:
            self.active_sessions.remove(user_id)
        if context.user_data:
            context.user_data.clear()
        logger.info(f"Cleaned up session for user {user_id}")

    async def handle_timeout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик таймаута сессии"""
        user = update.effective_user
        await self.cleanup_session(user.id, context)
        await context.bot.send_message(
            chat_id=user.id,
            text="⏳ Сессия бронирования закрыта из-за неактивности\n"
                 "Для нового бронирования используйте /add_booking"
        )

    async def start_add_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начало процесса бронирования с проверкой активных сессий"""
        try:
            user = update.effective_user
            logger.info(f"User {user.username} started add_booking")

            # Get the message object whether it's from a command or callback
            message = update.message or update.callback_query.message

            # Если у пользователя уже есть активная сессия
            if user.id in self.active_sessions:
                # Предлагаем продолжить или сбросить
                keyboard = [
                    [InlineKeyboardButton("🔄 Сбросить и начать новое", callback_data="force_new")],
                    [InlineKeyboardButton("❌ Отменить", callback_data="exit_command")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await message.reply_text(
                    "⚠️ У вас уже есть активная сессия бронирования.\n"
                    "Хотите сбросить её и начать новое бронирование?",
                    reply_markup=reply_markup
                )
                return SELECT_SHEET

            # Новая сессия
            self.active_sessions.add(user.id)
            context.user_data.clear()
            context.user_data["booking_date"] = datetime.now().strftime("%d.%m.%Y")

            # Создаем кнопки для выбора объекта из booking_objects
            keyboard = [
                [InlineKeyboardButton(sheet_name, callback_data=sheet_name)]
                for sheet_name in BOOKING_SHEETS.keys()
            ]
            # Добавляем кнопку выхода
            keyboard.append([InlineKeyboardButton("🚪 Выход", callback_data="exit_command")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await message.reply_text(
                "📋 Выберите объект для бронирования:",
                reply_markup=reply_markup
            )
            return SELECT_SHEET

        except Exception as e:
            logger.error(f"Error in start_add_booking: {e}", exc_info=True)
            message = update.message or update.callback_query.message
            await message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
            return ConversationHandler.END

    async def select_sheet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка выбора таблицы с обработкой команд сброса"""
        try:
            query = update.callback_query
            await query.answer()

            user = update.effective_user

            # Обработка команд управления сессией
            if query.data == "exit_command":
                return await self.handle_exit(update, context)
            elif query.data == "force_new":
                await self.cleanup_session(user.id, context)
                await query.edit_message_text("♻️ Предыдущая сессия сброшена. Начинаем новое бронирование.")
                return await self.start_add_booking(update, context)

            # Проверяем, что выбранный объект существует
            selected_sheet = query.data
            booking_sheet = get_booking_sheet(selected_sheet)
            if not booking_sheet:
                await query.edit_message_text("❌ Ошибка: выбранный объект не найден")
                return ConversationHandler.END

            context.user_data["sheet"] = selected_sheet
            context.user_data["booking_sheet"] = booking_sheet

            await query.edit_message_text(
                text=f"📌 Выбран объект: {selected_sheet}\n\n✏️ Введите имя гостя:"
            )
            return GUEST_NAME

        except Exception as e:
            logger.error(f"Error in select_sheet: {e}", exc_info=True)
            await self.cleanup_session(update.effective_user.id, context)
            await query.edit_message_text("⚠️ Ошибка выбора объекта")
            return ConversationHandler.END

    async def handle_exit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Универсальный обработчик выхода"""
        query = update.callback_query
        await query.answer()

        user = update.effective_user
        await self.cleanup_session(user.id, context)

        await query.edit_message_text(
            "🚪 Вы вышли из процесса бронирования.\n"
            "Для нового бронирования используйте /add_booking"
        )
        return ConversationHandler.END

    async def guest_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка ввода имени гостя"""
        try:
            guest_name = update.message.text.strip()
            if not guest_name:
                await update.message.reply_text("❌ Имя не может быть пустым. Попробуйте снова:")
                return GUEST_NAME

            context.user_data["guest"] = guest_name
            # Автоматически используем текущую дату и переходим к дате заезда
            await update.message.reply_text("🏨 Введите дату заезда (ДД.ММ.ГГГГ):")
            return CHECK_IN

        except Exception as e:
            logger.error(f"Error in guest_name: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки имени")
            return ConversationHandler.END

    async def booking_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка даты бронирования"""
        try:
            date_str = update.message.text.strip()
            if not date_str:
                date_str = datetime.now().strftime("%d.%m.%Y")

            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            formatted_date = date.strftime("%d.%m.%Y")
            context.user_data["booking_date"] = formatted_date

            await update.message.reply_text("🏨 Введите дату заезда (ДД.ММ.ГГГГ):")
            return CHECK_IN

        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return BOOKING_DATE
        except Exception as e:
            logger.error(f"Error in booking_date: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки даты")
            return ConversationHandler.END

    async def check_in(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка даты заезда"""
        try:
            date_str = update.message.text.strip()
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            formatted_date = date.strftime("%d.%m.%Y")
            context.user_data["check_in"] = formatted_date

            await update.message.reply_text("🚪 Введите дату выезда (ДД.ММ.ГГГГ):")
            return CHECK_OUT

        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return CHECK_IN
        except Exception as e:
            logger.error(f"Error in check_in: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки даты заезда")
            return ConversationHandler.END

    async def check_out(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка даты выезда с автоматическим расчетом количества ночей"""
        try:
            date_str = update.message.text.strip()
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            formatted_date = date.strftime("%d.%m.%Y")
            context.user_data["check_out"] = formatted_date

            # Автоматический расчет количества ночей
            check_in_str = context.user_data.get("check_in")
            if check_in_str:
                check_in_date = datetime.strptime(check_in_str, "%d.%m.%Y").date()
                nights = (date - check_in_date).days
                context.user_data["nights"] = str(nights)
                await update.message.reply_text(f"🌙 Рассчитанное количество ночей: {nights}")

            # Пропускаем шаг ввода количества ночей и переходим к следующему
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_monthly_sum")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="💰 Введите сумму по месяцам (например: 'Окт 15000 Ноя 20000'):",
                reply_markup=reply_markup,
            )
            return MONTHLY_SUM

        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return CHECK_OUT
        except Exception as e:
            logger.error(f"Error in check_out: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки даты выезда")
            return ConversationHandler.END

    async def nights(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка количества ночей"""
        try:
            nights = update.message.text.strip()
            if not nights.isdigit():
                await update.message.reply_text("❌ Введите число ночей:")
                return NIGHTS

            context.user_data["nights"] = nights

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_monthly_sum")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="💰 Введите сумму по месяцам (например: 'Окт 15000 Ноя 20000'):",
                reply_markup=reply_markup,
            )
            return MONTHLY_SUM

        except Exception as e:
            logger.error(f"Error in nights: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки количества ночей")
            return ConversationHandler.END

    async def skip_nights(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропуск ввода количества ночей"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🌙 Пропущено: количество ночей")

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_monthly_sum")]
        ])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="💰 Введите сумму по месяцам (например: 'Окт 15000 Ноя 20000'):",
            reply_markup=reply_markup,
        )
        return MONTHLY_SUM

    async def monthly_sum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка суммы по месяцам"""
        try:
            monthly_sum = update.message.text.strip()
            context.user_data["monthly_sum"] = monthly_sum

            await update.message.reply_text("💵 Введите общую сумму бронирования:")
            return TOTAL_SUM

        except Exception as e:
            logger.error(f"Error in monthly_sum: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки суммы по месяцам")
            return ConversationHandler.END

    async def skip_monthly_sum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропуск ввода суммы по месяцам"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("💰 Пропущено: сумма по месяцам")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="💵 Введите общую сумму бронирования:"
        )
        return TOTAL_SUM

    async def total_sum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка общей суммы"""
        try:
            total_sum = update.message.text.strip()
            context.user_data["total_sum"] = total_sum

            await update.message.reply_text("💳 Введите сумму аванса (в баттах/рублях):")
            return ADVANCE

        except Exception as e:
            logger.error(f"Error in total_sum: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки общей суммы")
            return ConversationHandler.END

    async def advance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка аванса"""
        try:
            advance = update.message.text.strip()
            context.user_data["advance"] = advance

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_additional_payment")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="💴 Введите сумму доплаты (если есть):",
                reply_markup=reply_markup,
            )
            return ADDITIONAL_PAYMENT

        except Exception as e:
            logger.error(f"Error in advance: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки аванса")
            return ConversationHandler.END

    async def additional_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка доплаты"""
        try:
            additional_payment = update.message.text.strip()
            context.user_data["additional_payment"] = additional_payment

            await update.message.reply_text("📌 Введите источник бронирования (Авито, Booking и т.д.):")
            return SOURCE

        except Exception as e:
            logger.error(f"Error in additional_payment: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки доплаты")
            return ConversationHandler.END

    async def skip_additional_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропуск ввода доплаты"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("💴 Пропущено: доплата")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📌 Введите источник бронирования (Авито, Booking и т.д.):",
        )
        return SOURCE

    async def source(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка источника бронирования"""
        try:
            source = update.message.text.strip()
            context.user_data["source"] = source

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_extra_charges")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="💸 Введите дополнительные платежи (если есть):",
                reply_markup=reply_markup,
            )
            return EXTRA_CHARGES

        except Exception as e:
            logger.error(f"Error in source: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки источника")
            return ConversationHandler.END

    async def extra_charges(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка дополнительных платежей"""
        try:
            extra_charges = update.message.text.strip()
            context.user_data["extra_charges"] = extra_charges

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_expenses")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🧹 Введите расходы (уборка и т.д.):",
                reply_markup=reply_markup,
            )
            return EXPENSES

        except Exception as e:
            logger.error(f"Error in extra_charges: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки доп. платежей")
            return ConversationHandler.END

    async def skip_extra_charges(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропуск ввода дополнительных платежей"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("💸 Пропущено: дополнительные платежи")

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_expenses")]
        ])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🧹 Введите расходы (уборка и т.д.):",
            reply_markup=reply_markup,
        )
        return EXPENSES

    async def expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка расходов"""
        try:
            expenses = update.message.text.strip()
            context.user_data["expenses"] = expenses

            await update.message.reply_text("💳 Введите способ оплаты:")
            return PAYMENT_METHOD

        except Exception as e:
            logger.error(f"Error in expenses: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки расходов")
            return ConversationHandler.END

    async def skip_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропуск ввода расходов"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🧹 Пропущено: расходы")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="💳 Введите способ оплаты:"
        )
        return PAYMENT_METHOD

    async def payment_method(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка способа оплаты"""
        try:
            payment_method = update.message.text.strip()
            context.user_data["payment_method"] = payment_method

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_comment")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📝 Введите комментарий (если есть):",
                reply_markup=reply_markup,
            )
            return COMMENT

        except Exception as e:
            logger.error(f"Error in payment_method: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки способа оплаты")
            return ConversationHandler.END

    async def comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка комментария"""
        try:
            comment = update.message.text.strip()
            context.user_data["comment"] = comment

            await update.message.reply_text("📱 Введите контактный телефон:")
            return PHONE

        except Exception as e:
            logger.error(f"Error in comment: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки комментария")
            return ConversationHandler.END

    async def skip_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропуск ввода комментария"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("📝 Пропущено: комментарий")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="📱 Введите контактный телефон:"
        )
        return PHONE

    async def phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка телефона"""
        try:
            phone = update.message.text.strip()
            context.user_data["phone"] = phone

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_extra_phone")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📱 Введите дополнительный телефон (если есть):",
                reply_markup=reply_markup,
            )
            return EXTRA_PHONE

        except Exception as e:
            logger.error(f"Error in phone: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки телефона")
            return ConversationHandler.END

    async def extra_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка дополнительного телефона"""
        try:
            extra_phone = update.message.text.strip()
            context.user_data["extra_phone"] = extra_phone

            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_flights")]
            ])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✈️ Введите информацию о рейсах (если есть):",
                reply_markup=reply_markup,
            )
            return FLIGHTS

        except Exception as e:
            logger.error(f"Error in extra_phone: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки доп. телефона")
            return ConversationHandler.END

    async def skip_extra_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропуск ввода дополнительного телефона"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("📱 Пропущено: дополнительный телефон")

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_flights")]
        ])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✈️ Введите информацию о рейсах (если есть):",
            reply_markup=reply_markup,
        )
        return FLIGHTS

    async def flights(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка информации о рейсах"""
        try:
            if update.callback_query and update.callback_query.data == "skip_flights":
                query = update.callback_query
                await query.answer()
                context.user_data["flights"] = ""
                await query.edit_message_text("✈️ Пропущено: информация о рейсах")
            else:
                flights = update.message.text.strip()
                context.user_data["flights"] = flights

            summary = self._generate_summary(context.user_data)

            keyboard = [
                [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")],
                [InlineKeyboardButton("❌ Отменить", callback_data="cancel")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📋 Проверьте данные бронирования:\n\n{summary}\n\nПодтверждаете?",
                reply_markup=reply_markup,
            )
            return CONFIRM

        except Exception as e:
            logger.error(f"Error in flights: {e}", exc_info=True)
            await update.message.reply_text("⚠️ Ошибка обработки информации о рейсах")
            return ConversationHandler.END

    async def skip_flights(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Пропустить ввод информации о рейсах"""
        return await self.flights(update, context)

    async def confirm_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Подтверждение бронирования с сохранением в CSV файл"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        if query.data == "cancel" or query.data == "exit_command":
            return await self.handle_exit(update, context)

        try:
            booking_sheet = context.user_data.get("booking_sheet")
            if not booking_sheet:
                await query.edit_message_text("❌ Ошибка: не указан объект для сохранения")
                return ConversationHandler.END

            # Сохраняем бронирование в CSV файл
            success = await self._save_booking_to_csv(booking_sheet, context.user_data)

            if success:
                await self.cleanup_session(user_id, context)
                await query.edit_message_text(
                    f"✅ Бронирование успешно создано для объекта '{booking_sheet.sheet_name}'!\n"
                    "Для нового бронирования используйте /add_booking"
                )
            else:
                await query.edit_message_text(
                    f"⚠️ Ошибка при сохранении бронирования для объекта '{booking_sheet.sheet_name}'\n"
                    "Попробуйте еще раз или обратитесь к администратору"
                )

            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error confirming booking: {e}", exc_info=True)
            await self.cleanup_session(user_id, context)
            await query.edit_message_text("⚠️ Ошибка при создании бронирования")
            return ConversationHandler.END

    async def _save_booking_to_csv(self, booking_sheet, user_data):
        """Сохраняет бронирование в CSV файл"""
        try:
            # Загружаем существующие данные
            df = booking_sheet.load()

            # Создаем новую запись
            new_booking = {
                'Гость': user_data.get('guest', ''),
                'Дата бронирования': user_data.get('booking_date', ''),
                'Заезд': user_data.get('check_in', ''),
                'Выезд': user_data.get('check_out', ''),
                'Количество ночей': user_data.get('nights', ''),
                'СуммаБатты': user_data.get('total_sum', ''),
                'Аванс Батты/Рубли': user_data.get('advance', ''),
                'Доплата Батты/Рубли': user_data.get('additional_payment', ''),
                'Источник': user_data.get('source', ''),
                'Дополнительные доплаты': user_data.get('extra_charges', ''),
                'Расходы': user_data.get('expenses', ''),
                'Оплата': user_data.get('payment_method', ''),
                'Комментарий': user_data.get('comment', ''),
                'телефон': user_data.get('phone', ''),
                'дополнительный телефон': user_data.get('extra_phone', ''),
                'Рейсы': user_data.get('flights', ''),
                '_sync_id': str(uuid.uuid4())  # Генерируем уникальный ID для синхронизации
            }

            # Добавляем новую запись в DataFrame
            new_df = pd.DataFrame([new_booking])
            df = pd.concat([df, new_df], ignore_index=True)

            # Сохраняем обратно в CSV
            booking_sheet.save(df)

            logger.info(f"Successfully saved booking to {booking_sheet.filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving booking to CSV: {e}", exc_info=True)
            return False

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка команды отмены с очисткой сессии"""
        user = update.effective_user
        await self.cleanup_session(user.id, context)

        await update.message.reply_text(
            "❌ Текущее бронирование отменено.\n"
            "Для нового бронирования используйте /add_booking"
        )
        return ConversationHandler.END

    def _generate_summary(self, data):
        """Генерация сводки данных"""
        return (
            f"Объект: {data.get('sheet', 'N/A')}\n"
            f"Гость: {data.get('guest', 'N/A')}\n"
            f"Дата бронирования: {data.get('booking_date', 'N/A')}\n"
            f"Дата заезда: {data.get('check_in', 'N/A')}\n"
            f"Дата выезда: {data.get('check_out', 'N/A')}\n"
            f"Количество ночей: {data.get('nights', 'N/A')}\n"
            f"Сумма по месяцам: {data.get('monthly_sum', 'N/A')}\n"
            f"Общая сумма: {data.get('total_sum', 'N/A')}\n"
            f"Аванс: {data.get('advance', 'N/A')}\n"
            f"Доплата: {data.get('additional_payment', 'N/A')}\n"
            f"Источник бронирования: {data.get('source', 'N/A')}\n"
            f"Доп. платежи: {data.get('extra_charges', 'N/A')}\n"
            f"Расходы: {data.get('expenses', 'N/A')}\n"
            f"Способ оплаты: {data.get('payment_method', 'N/A')}\n"
            f"Комментарий: {data.get('comment', 'N/A')}\n"
            f"Телефон: {data.get('phone', 'N/A')}\n"
            f"Доп. телефон: {data.get('extra_phone', 'N/A')}\n"
            f"Информация о рейсах: {data.get('flights', 'N/A')}"
        )