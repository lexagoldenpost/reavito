# commands.py
from telegram.ext import CommandHandler
from common.logging_config import setup_logger
from view_booking import view_booking_handler
from view_dates import view_dates_handler
from edit_booking import edit_booking_conv_handler  # Добавляем импорт обработчика редактирования

logger = setup_logger("commands")

COMMANDS = [
    ("start", "Начать работу с ботом"),
    ("add_booking", "Добавить бронирование"),
    ("view_booking", "Просмотр бронирования"),
    ("edit_booking", "Редактирование бронирования"),
    ("view_available_dates", "Просмотр свободных дат"),
    ("create_contract", "Создание договора"),
    ("help", "Помощь по командам"),
    ("cancel", "Сброс сессии бронирования"),
    ("sync_booking", "Синхронизировать бронирования"),
    ("exit", "Выход")
]

async def start(update, context):
    await update.message.reply_text(
        "Добро пожаловать! Доступные команды:\n\n" +
        "\n".join(f"/{cmd} - {desc}" for cmd, desc in COMMANDS if cmd != "start")
    )

async def help_command(update, context):
    await update.message.reply_text(
        "Доступные команды:\n\n" +
        "\n".join(f"/{cmd} - {desc}" for cmd, desc in COMMANDS)
    )

async def create_contract(update, context):
    await update.message.reply_text("ТЕСТ: Создание договора")

async def exit_bot(update, context):
    await update.message.reply_text("До свидания!")

def setup_command_handlers(application, bot):
    """Регистрация обработчиков команд"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("view_booking", view_booking_handler))
    application.add_handler(edit_booking_conv_handler)  # Заменяем простой обработчик на ConversationHandler
    application.add_handler(CommandHandler("view_available_dates", view_dates_handler))
    application.add_handler(CommandHandler("create_contract", create_contract))
    application.add_handler(CommandHandler("exit", exit_bot))

    logger.info("Command handlers setup completed")