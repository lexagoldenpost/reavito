from telegram.ext import CommandHandler
from common.logging_config import setup_logger

logger = setup_logger("commands")

COMMANDS = [
    ("start", "Начать работу с ботом"),
    ("add_booking", "Добавить бронирование"),
    ("view_booking", "Просмотр бронирования"),
    ("edit_booking", "Редактирование бронирования"),
    ("view_available_dates", "Просмотр свободных дат"),
    ("create_contract", "Создание договора"),
    ("help", "Помощь по командам"),
    ("exit", "Выход")
]


async def start(update, context):
    """Обработчик команды /start"""
    logger.info(f"User {update.effective_user.username} started the bot")
    await update.message.reply_text(
        "Добро пожаловать! Доступные команды:\n\n" +
        "\n".join(
            f"/{cmd} - {desc}" for cmd, desc in COMMANDS if cmd != "start")
    )


async def help_command(update, context):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "Доступные команды:\n\n" +
        "\n".join(f"/{cmd} - {desc}" for cmd, desc in COMMANDS)
    )


def setup_command_handlers(application, bot):
    """Регистрация обработчиков команд"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Здесь НЕ добавляем add_booking, так как это ConversationHandler
    application.add_handler(CommandHandler("view_booking", view_booking))
    application.add_handler(CommandHandler("edit_booking", edit_booking))
    application.add_handler(
        CommandHandler("view_available_dates", view_available_dates))
    application.add_handler(CommandHandler("create_contract", create_contract))
    application.add_handler(CommandHandler("exit", exit_bot))

    logger.info("Command handlers setup completed")

async def view_booking(update, context):
    await update.message.reply_text("ТЕСТ: Просмотр бронирования")

async def edit_booking(update, context):
    await update.message.reply_text("ТЕСТ: Редактирование бронирования")

async def view_available_dates(update, context):
    await update.message.reply_text("ТЕСТ: Просмотр свободных дат")

async def create_contract(update, context):
    await update.message.reply_text("ТЕСТ: Создание договора")

async def exit_bot(update, context):
    await update.message.reply_text("До свидания!")
