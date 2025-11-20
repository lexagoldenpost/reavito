# commands.py
from telegram.ext import CommandHandler

from common.logging_config import setup_logger
from main_tg_bot.command.sync_command import sync_handler
from main_tg_bot.command.view_booking import view_booking_handler
from main_tg_bot.command.view_dates import view_dates_handler
from main_tg_bot.command.new_menu import calculation_command

logger = setup_logger("commands")

COMMANDS = [
    ("start", "Начать работу с ботом"),
    ("view_booking", "Просмотр бронирования"),
    ("view_available_dates", "Просмотр свободных дат"),
    ("calculation", "Расчет, бронирования, договоры"),
    ("help", "Помощь по командам"),
    ("sync_booking", "Синхронизировать Гугл таблицы с локальными данными"),
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

async def exit_bot(update, context):
    await update.message.reply_text("До свидания!")

def setup_command_handlers(application, bot):
    """Регистрация обработчиков команд"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("view_booking", view_booking_handler))
    application.add_handler(CommandHandler("view_available_dates", view_dates_handler))
    application.add_handler(CommandHandler("calculation", calculation_command))  # Добавлен обработчик расчета
    application.add_handler(CommandHandler("exit", exit_bot))

    logger.info("Command handlers setup completed")