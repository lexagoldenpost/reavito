# booking_bot.py
import asyncio
import multiprocessing
import signal
import sys
import threading

from main_tg_bot.command.add_booking import AddBookingHandler
from main_tg_bot.command.sync_command import sync_handler
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

from main_tg_bot.command.commands import (
    COMMANDS,
    start,
    help_command,
    view_booking_handler,
    view_dates_handler,
    sync_handler,
    exit_bot,
)
from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
from main_tg_bot.scheduler.scheduler import AsyncScheduler

# Импортируем веб-сервер
try:
    from web_app_server import start_web_server, stop_web_server, wait_for_web_server
except ImportError:
    def start_web_server():
        print("❌ web_app_server.py не найден")
        return None

    def stop_web_server():
        pass

    def wait_for_web_server(timeout=30):
        return False

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
        self.web_server_started = False
        self.web_app_public_url = None
        logger.info("BookingBot initialized")
        logger.info(f"Token: {self.token[:10]}...")
        logger.info(f"Allowed users: {self.allowed_usernames}")

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

    def start_web_server(self):
        """Запуск веб-сервера для Web App с ожиданием готовности"""
        try:
            if not self.web_server_started:
                print("🔄 Запуск локального HTTPS веб-сервера...")

                # Попробуем принудительно сгенерировать сертификаты если нужно
                try:
                    from web_app_server import generate_ssl_certificates_force
                    generate_ssl_certificates_force()
                except Exception as e:
                    print(f"⚠️  Не удалось сгенерировать сертификаты: {e}")

                public_url = start_web_server()

                if public_url:
                    self.web_server_started = True
                    self.web_app_public_url = public_url
                    logger.info(f"Web server started: {public_url}")
                    return True
                else:
                    logger.error("Failed to start web server - no URL returned")
                    return False
            else:
                logger.info("Web server already running")
                return True
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
            return False

    def stop_web_server(self):
        """Остановка веб-сервера"""
        try:
            stop_web_server()
            self.web_server_started = False
            logger.info("Web server stopped")
        except Exception as e:
            logger.error(f"Error stopping web server: {e}")

    def run(self):
        """Запуск бота"""
        try:
            # Запускаем веб-сервер для Web App и проверяем успешность
            print("🔄 Запуск веб-сервера...")
            if not self.start_web_server():
                logger.error("Failed to start web server, bot cannot continue")
                return

            # Ждем полной готовности веб-сервера
            print("⏳ Ожидание готовности веб-сервера...")
            if not self.wait_for_web_server_ready(timeout=30):
                logger.error("Web server failed to become ready in time")
                return

            # Запускаем планировщик
            self.start_scheduler()

            # Настраиваем обработчик завершения
            def signal_handler(signum, frame):
                logger.info("Received shutdown signal")
                self.stop_scheduler()
                self.stop_web_server()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            self.setup_handlers()
            logger.info("Starting bot polling...")
            print("=" * 50)
            print("🤖 Бот запущен!")
            print(f"🌐 Локальный HTTPS сервер: {self.web_app_public_url}")
            print("⚠️  Внимание: Для работы Web App необходим HTTPS")
            print("📋 Доступные команды:")
            for cmd, desc in COMMANDS:
                print(f"   /{cmd} - {desc}")
            print("=" * 50)

            self.application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            self.stop_scheduler()
            self.stop_web_server()
            raise

    def get_web_app_url(self):
        """Получение URL веб-приложения"""
        if self.web_app_public_url:
            return self.web_app_public_url
        else:
            raise Exception("Web server not ready")

    def wait_for_web_server_ready(self, timeout=30):
        """Ожидание готовности веб-сервера"""
        try:
            if self.web_server_started and self.web_app_public_url:
                return True

            # Ждем готовности сервера
            return wait_for_web_server(timeout=timeout)
        except Exception as e:
            logger.error(f"Error waiting for web server: {e}")
            return False

    def start_scheduler(self):
        """Запуск планировщика в отдельном процессе"""
        try:
            # ИСПРАВЛЕННЫЙ ИМПОРТ - используем правильный путь
            from main_tg_bot.scheduler.scheduler import AsyncScheduler
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
    # Создаем экземпляр синхронизатора
    sync_manager = GoogleSheetsCSVSync(
        data_folder='booking_data'
    )

    # Синхронизация всех листов
    print("Синхронизация всех листов...")
    results = sync_manager.sync_all_sheets()
    print(f"Результаты: {results}")

    # Получение списка доступных листов
    available_sheets = sync_manager.get_available_sheets()
    print(f"\nДоступные листы: {available_sheets}")


if __name__ == "__main__":
    try:
        load_dotenv()
    except Exception as e:
        print(f"Error loading .env file: {e}")
        exit(1)
    try:
        logger.info("Sync booking start...")
        logger.info("Starting bot initialization...")
        # sync_google_sheets()
        bot = BookingBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        bot.stop_scheduler()
        bot.stop_web_server()
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)
        bot.stop_scheduler()
        bot.stop_web_server()