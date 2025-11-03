# main_tg_bot/command/new_menu.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from common.config import Config
from common.logging_config import setup_logger

logger = setup_logger("new_menu")


async def calculation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /calculation - показывает меню расчета"""
    await show_calculation_menu(update, context)


async def show_calculation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню расчета с кнопками, которые сразу открывают формы"""
    try:
        web_app_url = context.bot_data.get('web_app_url', '')

        if not web_app_url:
            if update.message:
                await update.message.reply_text("❌ URL веб-приложения не настроен")
            elif update.callback_query:
                await update.callback_query.edit_message_text("❌ URL веб-приложения не настроен")
            return

        # URL для форм
        calculation_url = f"{web_app_url}{Config.REMOTE_WEB_APP_BOOKING_CALCULATE_URL}"
        chess_url = f"{web_app_url}{Config.REMOTE_WEB_APP_BOOKING_CHESS_URL}"
        init_chat_id = update.effective_chat.id

        create_contract_url = f"{web_app_url}{Config.REMOTE_WEB_APP_CREATE_CONTRACT_URL}?token={Config.PHP_TELEGRAM_BOOKING_BOT_TOKEN}&chat_id={Config.TELEGRAM_DATA_CHANNEL_ID}&init_chat_id={init_chat_id}"
        #logger.info(f"✅ show_calculation_menu create_contract_url = '{create_contract_url}'")
        create_booking_url = f"{web_app_url}{Config.REMOTE_WEB_APP_CREATE_BOOKING_URL}?token={Config.PHP_TELEGRAM_BOOKING_BOT_TOKEN}&chat_id={Config.TELEGRAM_DATA_CHANNEL_ID}&init_chat_id={init_chat_id}"
        edit_booking_url = f"{web_app_url}{Config.REMOTE_WEB_APP_EDIT_BOOKING_URL}?token={Config.PHP_TELEGRAM_BOOKING_BOT_TOKEN}&chat_id={Config.TELEGRAM_DATA_CHANNEL_ID}&init_chat_id={init_chat_id}"
        # Кнопки, которые сразу открывают Web App
        keyboard = [
            [InlineKeyboardButton(
                "1. 🧮 Расчет стоимости",
                web_app=WebAppInfo(url=calculation_url)
            )],
            [InlineKeyboardButton(
                "2. 📊 Шахматка бронирования",
                web_app=WebAppInfo(url=chess_url)
            )],
            [InlineKeyboardButton(
                "3. 🗓️ Создание бронирования",
                web_app=WebAppInfo(url=create_booking_url)
            )],
            [InlineKeyboardButton(
                "4. ✏️ Редактирование бронирования",
                web_app=WebAppInfo(url=edit_booking_url)
            )],
            [InlineKeyboardButton(
                "5. 📑 Создание договора",
                web_app=WebAppInfo(url=create_contract_url)
            )],
            [InlineKeyboardButton("❌ Закрыть меню", callback_data="close_calculation_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "📈 *Расчеты*\n\n"
            "Выберите опцию:\n"
            "• *Расчет стоимости* - калькулятор стоимости бронирования\n"
            "• *Шахматка бронирования* - визуализация занятости\n\n"
            "• *Создание бронирования* - создание бронирования\n\n"
            "• *Редактирование бронирования* - редактирование/удаление бронирования\n\n"
            "• *Создание договора* - создание договора и подтверждения брони\n\n"
            "_Формы открываются автоматически при нажатии_"
        )

        if update.message:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error in show_calculation_menu: {e}")
        if update.message:
            await update.message.reply_text("❌ Произошла ошибка при загрузке меню расчета")


async def close_calculation_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для кнопки 'Закрыть меню' - удаляет сообщение с меню"""
    try:
        query = update.callback_query
        await query.answer()

        # Удаляем сообщение с меню
        await query.delete_message()

    except Exception as e:
        logger.error(f"Error in close_calculation_menu_handler: {e}")