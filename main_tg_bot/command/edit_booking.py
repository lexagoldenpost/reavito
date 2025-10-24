# edit_booking.py

import uuid
from datetime import datetime
import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

from common.logging_config import setup_logger
from main_tg_bot.booking_objects import BOOKING_SHEETS, get_booking_sheet
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync  # ← добавлен импорт

logger = setup_logger("edit_booking")

# Состояния для ConversationHandler
SELECT_SHEET, SELECT_BOOKING, EDIT_FIELD, EDIT_VALUE = range(4)


class EditBookingHandler:
    def __init__(self, bot):
        self.bot = bot
        self.sync_manager = GoogleSheetsCSVSync()  # ← инициализация синхронизатора

    def get_conversation_handler(self):
        """Создает и возвращает ConversationHandler"""
        return ConversationHandler(
            entry_points=[CommandHandler('edit_booking', self.edit_booking_start)],
            states={
                SELECT_SHEET: [CallbackQueryHandler(self.select_sheet, pattern="^sheet_")],
                SELECT_BOOKING: [
                    CallbackQueryHandler(self.select_booking, pattern="^booking_"),
                    CallbackQueryHandler(self.cancel_edit, pattern="^back_to_sheets")
                ],
                EDIT_FIELD: [
                    CallbackQueryHandler(self.select_field_to_edit, pattern="^edit_"),
                    CallbackQueryHandler(self.save_booking, pattern="^save_booking"),
                    CallbackQueryHandler(self.cancel_edit, pattern="^cancel_edit"),
                    CallbackQueryHandler(self.select_sheet, pattern="^back_to_bookings")
                ],
                EDIT_VALUE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.edit_field_value)
                ]
            },
            fallbacks=[CommandHandler('cancel', self.cancel_edit)],
            allow_reentry=True
        )

    def format_booking_data(self, booking_data):
        """Форматирование данных бронирования в читаемый вид"""
        try:
            nights = 0
            if booking_data.get('Заезд') and booking_data.get('Выезд'):
                try:
                    check_in = datetime.strptime(booking_data['Заезд'], "%d.%m.%Y").date()
                    check_out = datetime.strptime(booking_data['Выезд'], "%d.%m.%Y").date()
                    nights = (check_out - check_in).days
                except ValueError:
                    nights = 0

            message = (
                f"📋 Данные бронирования:\n\n"
                f"• Объект: {booking_data.get('sheet_name', 'N/A')}\n"
                f"• Гость: {booking_data.get('Гость', 'N/A')}\n"
                f"• Дата бронирования: {booking_data.get('Дата бронирования', 'N/A')}\n"
                f"• Заезд: {booking_data.get('Заезд', 'N/A')}\n"
                f"• Выезд: {booking_data.get('Выезд', 'N/A')}\n"
                f"• Ночей: {nights}\n"
                f"• Общая сумма: {booking_data.get('СуммаБатты', 'N/A')}\n"
                f"• Аванс: {booking_data.get('Аванс Батты/Рубли', 'N/A')}\n"
                f"• Доплата: {booking_data.get('Доплата Батты/Рубли', 'N/A')}\n"
                f"• Источник: {booking_data.get('Источник', 'N/A')}\n"
                f"• Доп. платежи: {booking_data.get('Дополнительные доплаты', 'N/A')}\n"
                f"• Расходы: {booking_data.get('Расходы', 'N/A')}\n"
                f"• Способ оплаты: {booking_data.get('Оплата', 'N/A')}\n"
                f"• Комментарий: {booking_data.get('Комментарий', 'N/A')}\n"
                f"• Телефон: {booking_data.get('телефон', 'N/A')}\n"
                f"• Доп. телефон: {booking_data.get('дополнительный телефон', 'N/A')}\n"
                f"• Рейсы: {booking_data.get('Рейсы', 'N/A')}\n"
                f"• ID: {booking_data.get('_sync_id', 'N/A')}"
            )
            return message
        except Exception as e:
            logger.error(f"Error formatting booking data: {e}")
            return "❌ Ошибка при форматировании данных бронирования"

    async def edit_booking_start(self, update: Update, context: CallbackContext) -> int:
        try:
            if not BOOKING_SHEETS:
                await update.message.reply_text("❌ Нет доступных объектов для редактирования.")
                return ConversationHandler.END

            keyboard = [
                [InlineKeyboardButton(sheet_name, callback_data=f"sheet_{sheet_name}")]
                for sheet_name in BOOKING_SHEETS.keys()
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "📋 Выберите объект для редактирования:",
                reply_markup=reply_markup
            )
            return SELECT_SHEET

        except Exception as e:
            logger.error(f"Error in edit_booking_start: {e}")
            await update.message.reply_text("❌ Ошибка при запуске редактирования.")
            return ConversationHandler.END

    async def select_sheet(self, update: Update, context: CallbackContext) -> int:
        try:
            query = update.callback_query
            await query.answer()

            if query.data == "back_to_sheets":
                return await self.edit_booking_start(update, context)

            sheet_name = query.data.replace("sheet_", "")
            booking_sheet = get_booking_sheet(sheet_name)

            if not booking_sheet:
                await query.edit_message_text("❌ Объект не найден.")
                return ConversationHandler.END

            df = booking_sheet.load()

            if df.empty:
                await query.edit_message_text("❌ Нет бронирований для этого объекта.")
                return ConversationHandler.END

            context.user_data['edit_booking'] = {
                'sheet_name': sheet_name,
                'booking_sheet': booking_sheet,
                'dataframe': df
            }

            keyboard = []
            for idx, row in df.iterrows():
                guest = row.get('Гость', 'Без имени')
                check_in = row.get('Заезд', 'N/A')
                check_out = row.get('Выезд', 'N/A')
                sync_id = row.get('_sync_id', str(idx))

                keyboard.append([InlineKeyboardButton(
                    f"🏠 {guest} ({check_in} - {check_out})",
                    callback_data=f"booking_{sync_id}"
                )])

            keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="back_to_sheets")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"📝 Выберите бронирование для {sheet_name}:",
                reply_markup=reply_markup
            )
            return SELECT_BOOKING

        except Exception as e:
            logger.error(f"Error in select_sheet: {e}")
            await update.callback_query.edit_message_text("❌ Ошибка при загрузке бронирований.")
            return ConversationHandler.END

    async def select_booking(self, update: Update, context: CallbackContext) -> int:
        try:
            query = update.callback_query
            await query.answer()

            if query.data == "back_to_bookings":
                return await self.select_sheet(update, context)

            sync_id = query.data.replace("booking_", "")
            user_data = context.user_data['edit_booking']
            df = user_data['dataframe']

            if '_sync_id' in df.columns:
                booking_row = df[df['_sync_id'] == sync_id]
            else:
                try:
                    idx = int(sync_id)
                    booking_row = df.iloc[[idx]]
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ Бронирование не найдено!")
                    return ConversationHandler.END

            if booking_row.empty:
                await query.edit_message_text("❌ Бронирование не найдено!")
                return ConversationHandler.END

            booking_data = booking_row.iloc[0].to_dict()
            booking_data['sheet_name'] = user_data['sheet_name']
            booking_data['row_index'] = booking_row.index[0]

            context.user_data['edit_booking']['current_booking'] = booking_data
            context.user_data['edit_booking']['original_data'] = booking_data.copy()

            message = self.format_booking_data(booking_data)
            keyboard = self._create_edit_keyboard(booking_data)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"{message}\n\n✏️ Выберите поле для редактирования:",
                reply_markup=reply_markup
            )
            return EDIT_FIELD

        except Exception as e:
            logger.error(f"Error in select_booking: {e}")
            await update.callback_query.edit_message_text("❌ Ошибка при выборе бронирования.")
            return ConversationHandler.END

    def _create_edit_keyboard(self, booking_data):
        fields = [
            ("Гость", "guest"),
            ("Дата бронирования", "booking_date"),
            ("Заезд", "check_in"),
            ("Выезд", "check_out"),
            ("СуммаБатты", "total_sum"),
            ("Аванс Батты/Рубли", "advance"),
            ("Доплата Батты/Рубли", "additional_payment"),
            ("Источник", "source"),
            ("Оплата", "payment_method"),
            ("Комментарий", "comment"),
            ("телефон", "phone"),
            ("дополнительный телефон", "extra_phone"),
            ("Рейсы", "flights")
        ]

        keyboard = []
        for field_name, field_key in fields:
            value = booking_data.get(field_name, 'N/A')
            if value and value != 'N/A':
                display_value = str(value)[:20] + "..." if len(str(value)) > 20 else str(value)
                keyboard.append([InlineKeyboardButton(
                    f"✏️ {field_name}: {display_value}",
                    callback_data=f"edit_{field_key}"
                )])

        keyboard.extend([
            [InlineKeyboardButton("✅ Сохранить изменения", callback_data="save_booking")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_edit")],
            [InlineKeyboardButton("↩️ Назад к списку", callback_data="back_to_bookings")]
        ])
        return keyboard

    async def select_field_to_edit(self, update: Update, context: CallbackContext) -> int:
        try:
            query = update.callback_query
            await query.answer()

            if query.data == "back_to_bookings":
                return await self.select_sheet(update, context)
            if query.data == "cancel_edit":
                return await self.cancel_edit(update, context)
            if query.data == "save_booking":
                return await self.save_booking(update, context)

            field_key = query.data.replace("edit_", "")
            context.user_data['edit_booking']['current_field'] = field_key

            field_names = {
                "guest": "Гость",
                "booking_date": "Дата бронирования (ДД.ММ.ГГГГ)",
                "check_in": "Дата заезда (ДД.ММ.ГГГГ)",
                "check_out": "Дата выезда (ДД.ММ.ГГГГ)",
                "total_sum": "Общая сумма",
                "advance": "Аванс",
                "additional_payment": "Доплата",
                "source": "Источник бронирования",
                "payment_method": "Способ оплаты",
                "comment": "Комментарий",
                "phone": "Телефон",
                "extra_phone": "Дополнительный телефон",
                "flights": "Информация о рейсах"
            }

            booking_data = context.user_data['edit_booking']['current_booking']
            current_value = booking_data.get(field_names.get(field_key, field_key), 'N/A')

            await query.edit_message_text(
                f"✏️ Введите новое значение для поля '{field_names.get(field_key, field_key)}':\n"
                f"📌 Текущее значение: {current_value}\n\n"
                f"💡 Для отмены используйте /cancel"
            )
            return EDIT_VALUE

        except Exception as e:
            logger.error(f"Error in select_field_to_edit: {e}")
            await update.callback_query.edit_message_text("❌ Ошибка при выборе поля.")
            return ConversationHandler.END

    async def edit_field_value(self, update: Update, context: CallbackContext) -> int:
        try:
            new_value = update.message.text.strip()
            field_key = context.user_data['edit_booking']['current_field']
            booking_data = context.user_data['edit_booking']['current_booking']

            field_mapping = {
                "guest": "Гость",
                "booking_date": "Дата бронирования",
                "check_in": "Заезд",
                "check_out": "Выезд",
                "total_sum": "СуммаБатты",
                "advance": "Аванс Батты/Рубли",
                "additional_payment": "Доплата Батты/Рубли",
                "source": "Источник",
                "payment_method": "Оплата",
                "comment": "Комментарий",
                "phone": "телефон",
                "extra_phone": "дополнительный телефон",
                "flights": "Рейсы"
            }

            csv_field_name = field_mapping.get(field_key, field_key)

            # Валидация дат
            date_fields = ["booking_date", "check_in", "check_out"]
            if field_key in date_fields:
                try:
                    parsed_date = datetime.strptime(new_value, "%d.%m.%Y").date()
                except ValueError:
                    await update.message.reply_text(
                        "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ\nПопробуйте снова:"
                    )
                    return EDIT_VALUE

                # 🔴 Дополнительная проверка для заезда и выезда
                if field_key in ("check_in", "check_out"):
                    # Получаем текущие даты из booking_data
                    current_check_in = booking_data.get("Заезд")
                    current_check_out = booking_data.get("Выезд")

                    if field_key == "check_in":
                        new_check_in = parsed_date
                        # Используем текущую дату выезда или новую, если она уже задана
                        check_out_str = current_check_out
                    else:  # field_key == "check_out"
                        new_check_out = parsed_date
                        check_out_str = new_value
                        check_in_str = current_check_in

                    # Проверяем пару дат
                    if field_key == "check_in":
                        if current_check_out:
                            try:
                                check_out_date = datetime.strptime(current_check_out, "%d.%m.%Y").date()
                                if check_out_date < new_check_in:
                                    await update.message.reply_text(
                                        "❌ Дата выезда не может быть раньше новой даты заезда.\n"
                                        "Сначала обновите дату выезда, или введите корректную дату заезда:"
                                    )
                                    return EDIT_VALUE
                            except ValueError:
                                pass  # если текущая дата выезда некорректна — пропускаем проверку
                    elif field_key == "check_out":
                        if current_check_in:
                            try:
                                check_in_date = datetime.strptime(current_check_in, "%d.%m.%Y").date()
                                if new_check_out < check_in_date:
                                    await update.message.reply_text(
                                        "❌ Дата выезда не может быть раньше даты заезда.\n"
                                        "Введите корректную дату выезда:"
                                    )
                                    return EDIT_VALUE
                            except ValueError:
                                pass

                booking_data[csv_field_name] = new_value
            else:
                booking_data[csv_field_name] = new_value

            context.user_data['edit_booking']['current_booking'] = booking_data
            return await self.show_booking_for_edit(update, context)

        except Exception as e:
            logger.error(f"Error in edit_field_value: {e}")
            await update.message.reply_text("❌ Ошибка при сохранении значения.")
            return EDIT_VALUE

    async def show_booking_for_edit(self, update: Update, context: CallbackContext) -> int:
        try:
            booking_data = context.user_data['edit_booking']['current_booking']
            message = self.format_booking_data(booking_data)
            keyboard = self._create_edit_keyboard(booking_data)
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{message}\n\n✏️ Выберите поле для редактирования:",
                reply_markup=reply_markup
            )
            return EDIT_FIELD

        except Exception as e:
            logger.error(f"Error in show_booking_for_edit: {e}")
            await update.message.reply_text("❌ Ошибка при отображении данных.")
            return ConversationHandler.END

    async def save_booking(self, update: Update, context: CallbackContext) -> int:
        try:
            query = update.callback_query
            await query.answer()

            user_data = context.user_data['edit_booking']
            booking_data = user_data['current_booking']
            original_data = user_data['original_data']
            booking_sheet = user_data['booking_sheet']
            df = user_data['dataframe']
            sheet_name = user_data['sheet_name']

            row_index = booking_data['row_index']

            # 🔴 Финальная проверка дат
            check_in_str = booking_data.get("Заезд")
            check_out_str = booking_data.get("Выезд")
            if check_in_str and check_out_str:
                try:
                    check_in = datetime.strptime(check_in_str, "%d.%m.%Y").date()
                    check_out = datetime.strptime(check_out_str, "%d.%m.%Y").date()
                    if check_out < check_in:
                        await query.edit_message_text(
                            "❌ Ошибка: дата выезда раньше даты заезда. Исправьте данные и попробуйте снова."
                        )
                        return EDIT_FIELD
                except ValueError:
                    pass

            # Сохраняем в CSV
            for key, value in booking_data.items():
                if key not in ['sheet_name', 'row_index'] and key in df.columns:
                    df.at[row_index, key] = value

            booking_sheet.save(df)

            # 📥 Сообщаем о локальном сохранении
            changes = []
            for key in booking_data.keys():
                if key not in ['sheet_name', 'row_index']:
                    orig = str(original_data.get(key, ''))
                    new = str(booking_data.get(key, ''))
                    if orig != new:
                        changes.append(f"• {key}: '{orig}' → '{new}'")

            if changes:
                changes_text = "\n".join(changes)
                await query.edit_message_text(
                    f"✅ Бронирование обновлено и сохранено в локальный файл:\n"
                    f"📁 {booking_sheet.filename}\n\n"
                    f"📝 Изменения:\n{changes_text}"
                )
            else:
                await query.edit_message_text(
                    f"✅ Данные сохранены в локальный файл (изменений не было):\n"
                    f"📁 {booking_sheet.filename}"
                )

            # 🔁 Синхронизация
            sync_success = self.sync_manager.sync_sheet(sheet_name, direction='csv_to_google')

            # 📤 Отдельное сообщение о синхронизации
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

            if 'edit_booking' in context.user_data:
                del context.user_data['edit_booking']

            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error in save_booking: {e}", exc_info=True)
            await query.edit_message_text("❌ Ошибка при сохранении изменений.")
            return ConversationHandler.END

    async def cancel_edit(self, update: Update, context: CallbackContext) -> int:
        try:
            query = update.callback_query
            if query:
                await query.answer()
                await query.edit_message_text("❌ Редактирование отменено. Изменения не сохранены.")
            else:
                await update.message.reply_text("❌ Редактирование отменено.")

            if 'edit_booking' in context.user_data:
                del context.user_data['edit_booking']

            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error in cancel_edit: {e}")
            if update.message:
                await update.message.reply_text("❌ Редактирование отменено.")
            return ConversationHandler.END