# booking_bot.py
import asyncio
import multiprocessing
import signal
import sys

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.command.add_booking import AddBookingHandler
from main_tg_bot.command.commands import (
    COMMANDS,
    start,
    help_command,
    view_booking_handler,
    view_dates_handler,
    sync_handler,
    exit_bot,
)
from main_tg_bot.command.edit_booking import EditBookingHandler
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
from scheduler.scheduler import AsyncScheduler

logger = setup_logger("booking_bot")

# Добавляем префиксы для callback-данных
CALLBACK_PREFIX = "sb_"  # sb = send_bookings
VB_CALLBACK_PREFIX = "vb_"  # vb = view_booking


class BookingBot:
    def __init__(self):
        self.token = Config.TELEGRAM_BOOKING_BOT_TOKEN
        self.allowed_usernames = [u.lower() for u in
                                  Config.ALLOWED_TELEGRAM_USERNAMES]
        self.application = None
        self.scheduler_process = None
        # Удаленный веб-сервер уже запущен, не нужно запускать локальный
        self.remote_web_app_url = Config.REMOTE_WEB_APP_URL
        logger.info("BookingBot initialized")
        logger.info(f"Token: {self.token[:10]}...")
        logger.info(f"Allowed users: {self.allowed_usernames}")
        logger.info(f"Remote web app URL: {self.remote_web_app_url}")

    async def check_user_permission(self, update):
        """Проверка прав доступа пользователя"""
        user = update.effective_user
        if not user:
            logger.warning("No user in update")
            return False

        logger.info(
            f"Checking permission for user: {user.username} (ID: {user.id})")

        if not user.username:
            if update.callback_query:
                await update.callback_query.answer(
                    "У вас не установлен username в Telegram.", show_alert=True)
            elif update.message:
                await update.message.reply_text(
                    "У вас не установлен username в Telegram.")
            return False

        if user.username.lower() not in self.allowed_usernames:
            if update.callback_query:
                await update.callback_query.answer("У вас нет доступа к этому боту.",
                                                   show_alert=True)
            elif update.message:
                await update.message.reply_text("У вас нет доступа к этому боту.")
            return False

        return True

    async def _secure_handler_wrapper(self, handler, update, context):
        """Обертка для обработчиков с проверкой прав доступа"""
        if not await self.check_user_permission(update):
            return None
        return await handler(update, context)

    def _add_secure_command_handler(self, command, handler):
        """Добавляет обработчик команды с проверкой прав доступа"""
        wrapped_handler = lambda update, context: self._secure_handler_wrapper(
            handler, update, context)
        self.application.add_handler(CommandHandler(command, wrapped_handler))

    def _add_secure_callback_handler(self, handler, pattern=None):
        """Добавляет обработчик callback с проверкой прав доступа и фильтром"""
        wrapped_handler = lambda update, context: self._secure_handler_wrapper(
            handler, update, context)

        if pattern:
            self.application.add_handler(
                CallbackQueryHandler(wrapped_handler, pattern=pattern))
        else:
            self.application.add_handler(CallbackQueryHandler(wrapped_handler))

    def setup_handlers(self):
        """Настройка всех обработчиков с проверкой прав доступа"""
        self.application = Application.builder().token(self.token).build()

        # 1. Обработчики команд с проверкой доступа
        self._add_secure_command_handler("start", start)
        self._add_secure_command_handler("help", help_command)
        self._add_secure_command_handler("view_booking", view_booking_handler)
        self._add_secure_command_handler("view_available_dates", view_dates_handler)
        self._add_secure_command_handler("sync_booking", sync_handler)
        self._add_secure_command_handler("exit", exit_bot)

        # 2. ConversationHandler для add_booking
        booking_handler = AddBookingHandler(self)
        self.application.add_handler(booking_handler.get_conversation_handler())

        # 3. Добавляем обработчик редактирования бронирования
        edit_handler = EditBookingHandler(self)
        self.application.add_handler(edit_handler.get_conversation_handler())

        # 3. CallbackHandler для view_booking с фильтром по префиксу
        self._add_secure_callback_handler(
            view_booking_handler,
            pattern=f"^{VB_CALLBACK_PREFIX}.*"
        )

        # 4. Обработчик неизвестных команд
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_command)
        )

        logger.info("Handlers setup completed")

    async def unknown_command(self, update, context):
        """Обработка неизвестных команд"""
        if not update.message:
            return

        logger.warning(
            f"Unknown text from {update.effective_user.username}: {update.message.text}")
        await update.message.reply_text(
            "Неизвестная команда. Доступные команды:\n\n" +
            "\n".join(f"/{cmd} - {desc}" for cmd, desc in COMMANDS)
        )

    def get_web_app_url(self):
        """Получение URL удаленного веб-приложения"""
        if self.remote_web_app_url:
            return self.remote_web_app_url
        else:
            raise Exception("Remote web app URL not configured")

    def run(self):
        """Запуск бота"""
        try:
            # Проверяем наличие URL удаленного сервера
            if not self.remote_web_app_url:
                logger.error("Remote web app URL not configured, bot cannot continue")
                return

            # Запускаем планировщик
            self.start_scheduler()

            # Настраиваем обработчик завершения
            def signal_handler(signum, frame):
                logger.info("Received shutdown signal")
                self.stop_scheduler()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            self.setup_handlers()
            logger.info("Starting bot polling...")
            print("=" * 50)
            print("🤖 Бот запущен!")
            print(f"🌐 Удаленный сервер форм: {self.remote_web_app_url}")
            print("📋 Доступные команды:")
            for cmd, desc in COMMANDS:
                print(f"   /{cmd} - {desc}")
            print("=" * 50)

            self.application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            self.stop_scheduler()
            raise

    def start_scheduler(self):
        """Запуск планировщика в отдельном процессе"""
        try:
            from scheduler.scheduler import AsyncScheduler
            self.scheduler_process = multiprocessing.Process(
                target=self._run_scheduler,
                name="SchedulerProcess"
            )
            self.scheduler_process.start()
            logger.info("Scheduler started in separate process")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")

    def _run_scheduler(self):
        """Запуск асинхронного планировщика в отдельном процессе"""
        try:
            scheduler = AsyncScheduler()
            asyncio.run(scheduler.run())
        except Exception as e:
            logger.error(f"Scheduler process error: {e}")

    def stop_scheduler(self):
        """Остановка планировщика"""
        if self.scheduler_process and self.scheduler_process.is_alive():
            self.scheduler_process.terminate()
            self.scheduler_process.join()
            logger.info("Scheduler stopped")


def sync_google_sheets():
    """Выполняет синхронизацию всех листов Google Sheets с локальными CSV."""
    try:
        # Создаём экземпляр синхронизатора (без data_folder — пути теперь фиксированы)
        sync_manager = GoogleSheetsCSVSync()

        # Синхронизация всех листов
        logger.info("Starting full Google Sheets sync...")
        results = sync_manager.sync_all_sheets()
        success_count = sum(results.values())
        total_count = len(results)
        logger.info(f"Sync completed: {success_count}/{total_count} sheets successful")
        print(f"✅ Синхронизация завершена: {success_count}/{total_count} листов")

        # Опционально: выводим список доступных листов
        available_sheets = sync_manager.get_available_sheets()
        logger.debug(f"Available sheets: {available_sheets}")
    except Exception as e:
        logger.error(f"Ошибка при синхронизации Google Sheets: {e}", exc_info=True)
        print(f"❌ Ошибка синхронизации: {e}")
        raise

if __name__ == "__main__":
    try:
        load_dotenv()
    except Exception as e:
        print(f"Error loading .env file: {e}")
        exit(1)
    try:
        logger.info("Sync booking start...")
        logger.info("Starting bot initialization...")
        #Запускать только если все данные в гугл таблице актальнее чем локально. Напрмиер при первичной загрузке иначе из локала перетрет
        sync_google_sheets()
        bot = BookingBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        bot.stop_scheduler()
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)
        bot.stop_scheduler()
