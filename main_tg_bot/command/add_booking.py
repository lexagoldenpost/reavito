# add_booking.py

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

# Импортируем синхронизатор
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync

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
        # Инициализируем синхронизатор один раз
        self.sync_manager = GoogleSheetsCSVSync()

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
            fallbacks=[
                CommandHandler("cancel", self.handle_cancel_anywhere),
                MessageHandler(filters.Regex(r"^/cancel$"), self.handle_cancel_anywhere),
            ],
            conversation_timeout=300,
            allow_reentry=True,
        )

    async def handle_cancel_anywhere(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user = update.effective_user
        context.user_data.clear()
        logger.info(f"Booking cancelled by user {user.id}")

        message = update.message or (update.callback_query and update.callback_query.message)
        if message:
            await message.reply_text(
                "❌ Текущее бронирование отменено.\n"
                "Для нового бронирования используйте /add_booking"
            )
        return ConversationHandler.END

    async def start_add_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            user = update.effective_user
            logger.info(f"User {user.username or user.id} started add_booking")

            context.user_data.clear()
            context.user_data["booking_date"] = datetime.now().strftime("%d.%m.%Y")

            message = update.message or update.callback_query.message

            keyboard = [
                [InlineKeyboardButton(sheet_name, callback_data=sheet_name)]
                for sheet_name in BOOKING_SHEETS.keys()
            ]
            keyboard.append([InlineKeyboardButton("🚪 Выход", callback_data="exit_command")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await message.reply_text(
                "📋 Выберите объект для бронирования:",
                reply_markup=reply_markup
            )
            return SELECT_SHEET

        except Exception as e:
            logger.error(f"Error in start_add_booking: {e}", exc_info=True)
            message = update.message or (update.callback_query and update.callback_query.message)
            if message:
                await message.reply_text("⚠️ Произошла ошибка. Попробуйте позже.")
            return ConversationHandler.END

    async def select_sheet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            query = update.callback_query
            await query.answer()

            if query.data == "exit_command":
                return await self.handle_exit(update, context)

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
            await query.edit_message_text("⚠️ Ошибка выбора объекта")
            return ConversationHandler.END

    async def handle_exit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data.clear()
        await query.edit_message_text(
            "🚪 Вы вышли из процесса бронирования.\n"
            "Для нового бронирования используйте /add_booking"
        )
        return ConversationHandler.END

    async def guest_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        guest_name = update.message.text.strip()
        if not guest_name:
            await update.message.reply_text("❌ Имя не может быть пустым. Попробуйте снова:")
            return GUEST_NAME
        context.user_data["guest"] = guest_name
        await update.message.reply_text("🏨 Введите дату заезда (ДД.ММ.ГГГГ):")
        return CHECK_IN

    async def booking_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            date_str = update.message.text.strip()
            if not date_str:
                date_str = datetime.now().strftime("%d.%m.%Y")
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            context.user_data["booking_date"] = date.strftime("%d.%m.%Y")
            await update.message.reply_text("🏨 Введите дату заезда (ДД.ММ.ГГГГ):")
            return CHECK_IN
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return BOOKING_DATE

    async def check_in(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            date_str = update.message.text.strip()
            date = datetime.strptime(date_str, "%d.%m.%Y").date()
            context.user_data["check_in"] = date.strftime("%d.%m.%Y")
            await update.message.reply_text("🚪 Введите дату выезда (ДД.ММ.ГГГГ):")
            return CHECK_OUT
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ:")
            return CHECK_IN

    async def check_out(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            date_str = update.message.text.strip()
            check_out_date = datetime.strptime(date_str, "%d.%m.%Y").date()
            check_in_str = context.user_data.get("check_in")
            if not check_in_str:
                await update.message.reply_text("❌ Сначала укажите дату заезда.")
                return CHECK_OUT

            check_in_date = datetime.strptime(check_in_str, "%d.%m.%Y").date()

            # 🔴 Проверка: выезд не может быть раньше заезда
            if check_out_date < check_in_date:
                await update.message.reply_text(
                    "❌ Дата выезда не может быть раньше даты заезда.\n"
                    "Пожалуйста, введите корректную дату выезда:"
                )
                return CHECK_OUT

            formatted_date = check_out_date.strftime("%d.%m.%Y")
            context.user_data["check_out"] = formatted_date

            nights = (check_out_date - check_in_date).days
            context.user_data["nights"] = str(nights)
            await update.message.reply_text(f"🌙 Рассчитанное количество ночей: {nights}")

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

    async def skip_nights(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        context.user_data["monthly_sum"] = update.message.text.strip()
        await update.message.reply_text("💵 Введите общую сумму бронирования:")
        return TOTAL_SUM

    async def skip_monthly_sum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("💰 Пропущено: сумма по месяцам")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="💵 Введите общую сумму бронирования:"
        )
        return TOTAL_SUM

    async def total_sum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["total_sum"] = update.message.text.strip()
        await update.message.reply_text("💳 Введите сумму аванса (в баттах/рублях):")
        return ADVANCE

    async def advance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["advance"] = update.message.text.strip()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_additional_payment")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="💴 Введите сумму доплаты (если есть):",
            reply_markup=reply_markup,
        )
        return ADDITIONAL_PAYMENT

    async def additional_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["additional_payment"] = update.message.text.strip()
        await update.message.reply_text("📌 Введите источник бронирования (Авито, Booking и т.д.):")
        return SOURCE

    async def skip_additional_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("💴 Пропущено: доплата")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📌 Введите источник бронирования (Авито, Booking и т.д.):",
        )
        return SOURCE

    async def source(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["source"] = update.message.text.strip()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_extra_charges")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="💸 Введите дополнительные платежи (если есть):",
            reply_markup=reply_markup,
        )
        return EXTRA_CHARGES

    async def extra_charges(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["extra_charges"] = update.message.text.strip()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_expenses")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🧹 Введите расходы (уборка и т.д.):",
            reply_markup=reply_markup,
        )
        return EXPENSES

    async def skip_extra_charges(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        context.user_data["expenses"] = update.message.text.strip()
        await update.message.reply_text("💳 Введите способ оплаты:")
        return PAYMENT_METHOD

    async def skip_expenses(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🧹 Пропущено: расходы")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="💳 Введите способ оплаты:"
        )
        return PAYMENT_METHOD

    async def payment_method(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["payment_method"] = update.message.text.strip()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_comment")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📝 Введите комментарий (если есть):",
            reply_markup=reply_markup,
        )
        return COMMENT

    async def comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["comment"] = update.message.text.strip()
        await update.message.reply_text("📱 Введите контактный телефон:")
        return PHONE

    async def skip_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("📝 Пропущено: комментарий")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="📱 Введите контактный телефон:"
        )
        return PHONE

    async def phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["phone"] = update.message.text.strip()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_extra_phone")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📱 Введите дополнительный телефон (если есть):",
            reply_markup=reply_markup,
        )
        return EXTRA_PHONE

    async def extra_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data["extra_phone"] = update.message.text.strip()
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_flights")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✈️ Введите информацию о рейсах (если есть):",
            reply_markup=reply_markup,
        )
        return FLIGHTS

    async def skip_extra_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        if update.callback_query and update.callback_query.data == "skip_flights":
            query = update.callback_query
            await query.answer()
            context.user_data["flights"] = ""
            await query.edit_message_text("✈️ Пропущено: информация о рейсах")
        else:
            context.user_data["flights"] = update.message.text.strip()

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

    async def skip_flights(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return await self.flights(update, context)

    async def confirm_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()

        if query.data in ("cancel", "exit_command"):
            return await self.handle_exit(update, context)

        try:
            booking_sheet = context.user_data.get("booking_sheet")
            if not booking_sheet:
                await query.edit_message_text("❌ Ошибка: не указан объект для сохранения")
                return ConversationHandler.END

            success = await self._save_booking_to_csv(booking_sheet, context.user_data)

            if success:
                sheet_name = context.user_data["sheet"]
                # 📥 Сначала сообщаем о локальном сохранении
                await query.edit_message_text(
                    f"✅ Бронирование успешно сохранено в локальный файл:\n"
                    f"📁 {booking_sheet.filename}"
                )

                # 🔁 Затем запускаем синхронизацию
                sync_success = self.sync_manager.sync_sheet(sheet_name, direction='csv_to_google')

                # 📤 Отправляем отдельное сообщение о синхронизации
                if sync_success:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="✅ Данные успешно синхронизированы с Google Таблицей!"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="⚠️ Синхронизация с Google Таблицей не удалась.\n"
                             "Данные сохранены локально. Повторите синхронизацию позже."
                    )
            else:
                await query.edit_message_text(
                    "❌ Ошибка сохранения бронирования. Попробуйте позже."
                )
            context.user_data.clear()
            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error in confirm_booking: {e}", exc_info=True)
            await query.edit_message_text("❌ Ошибка сохранения бронирования")
            return ConversationHandler.END

    async def _save_booking_to_csv(self, booking_sheet, user_data):
        try:
            import os
            filepath = booking_sheet.filepath
            columns = [
                'Гость', 'Дата бронирования', 'Заезд', 'Выезд', 'Количество ночей',
                'СуммаБатты', 'Аванс Батты/Рубли', 'Доплата Батты/Рубли', 'Источник',
                'Дополнительные доплаты', 'Расходы', 'Оплата', 'Комментарий',
                'телефон', 'дополнительный телефон', 'Рейсы', '_sync_id'
            ]

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                df = pd.DataFrame(columns=columns)
            else:
                df = booking_sheet.load()

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
                '_sync_id': str(uuid.uuid4())
            }

            new_df = pd.DataFrame([new_booking])
            df = pd.concat([df, new_df], ignore_index=True)
            booking_sheet.save(df)
            logger.info(f"Successfully saved booking to {booking_sheet.filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving booking to CSV: {e}", exc_info=True)
            return False

    def _generate_summary(self, user_data):
        summary = []
        fields = [
            ("Объект", "sheet"),
            ("Гость", "guest"),
            ("Дата бронирования", "booking_date"),
            ("Заезд", "check_in"),
            ("Выезд", "check_out"),
            ("Количество ночей", "nights"),
            ("Сумма по месяцам", "monthly_sum"),
            ("Общая сумма", "total_sum"),
            ("Аванс", "advance"),
            ("Доплата", "additional_payment"),
            ("Источник", "source"),
            ("Доп. платежи", "extra_charges"),
            ("Расходы", "expenses"),
            ("Способ оплаты", "payment_method"),
            ("Комментарий", "comment"),
            ("Телефон", "phone"),
            ("Доп. телефон", "extra_phone"),
            ("Рейсы", "flights"),
        ]
        for label, key in fields:
            value = user_data.get(key)
            if value:
                summary.append(f"• {label}: {value}")
        return "\n".join(summary)