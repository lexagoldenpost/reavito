# main.py
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler
)
from common.config import Config
from common.logging_config import setup_logger
from commands import setup_command_handlers, COMMANDS
from add_booking import AddBookingHandler
from view_booking import view_booking_handler
from sync_google_booking import process_google_sheets_to_db

logger = setup_logger("main")


class BookingBot:
    def __init__(self):
        self.token = Config.TELEGRAM_BOOKING_BOT_TOKEN
        self.allowed_usernames = [u.lower() for u in
                                Config.ALLOWED_TELEGRAM_USERNAMES]
        self.application = None
        logger.info("BookingBot initialized")
        logger.info(
            f"Token: {self.token[:10]}...")  # Логируем часть токена для проверки
        logger.info(f"Allowed users: {self.allowed_usernames}")

    async def check_user_permission(self, update):
        user = update.effective_user
        logger.info(
            f"Checking permission for user: {user.username} (ID: {user.id})")
        if not user.username:
            await update.message.reply_text(
                "У вас не установлен username в Telegram.")
            return False
        if user.username.lower() not in self.allowed_usernames:
            await update.message.reply_text("У вас нет доступа к этому боту.")
            return False
        return True

    def setup_handlers(self):
        """Настройка всех обработчиков"""
        self.application = Application.builder().token(self.token).build()

        # 1. Сначала добавляем обработчик команд
        setup_command_handlers(self.application, self)

        # 2. Затем добавляем ConversationHandler для add_booking
        booking_handler = AddBookingHandler(self)
        self.application.add_handler(booking_handler.get_conversation_handler())

        # 3. Добавляем обработчик для view_booking
        self.application.add_handler(CallbackQueryHandler(view_booking_handler))

        # 4. Обработчик неизвестных команд (должен быть последним)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_command)
        )

        logger.info("Handlers setup completed")

    async def unknown_command(self, update, context):
        """Обработка неизвестных команд"""
        logger.warning(
            f"Unknown text from {update.effective_user.username}: {update.message.text}")
        await update.message.reply_text(
            "Неизвестная команда. Доступные команды:\n\n" +
            "\n".join(f"/{cmd} - {desc}" for cmd, desc in COMMANDS)
        )

    def run(self):
        """Запуск бота"""
        try:
            self.setup_handlers()
            logger.info("Starting bot polling...")
            print("Бот запущен. Доступные команды:")
            for cmd, desc in COMMANDS:
                print(f"/{cmd} - {desc}")

            self.application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    try:
        logger.info("Sync booking start...")
        process_google_sheets_to_db()
        logger.info("Starting bot initialization...")
        bot = BookingBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)