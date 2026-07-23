# booking_bot.py - исправленная версия

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

from common.config import Config
from common.logging_config import setup_logger
from main_tg_bot.command.commands import (
    COMMANDS,
    start,
    help_command,
    view_booking_handler,
    view_dates_handler,
    sync_handler,
    exit_bot,
)
from main_tg_bot.google_sheets.sync_manager import GoogleSheetsCSVSync
from main_tg_bot.command.new_menu import (
    calculation_command,
    close_calculation_menu_handler
)

# НЕ ИНИЦИАЛИЗИРУЕМ telegram_client здесь - он будет инициализирован при первом использовании
# from telega.telegram_client import telegram_client

logger = setup_logger("booking_bot")

# Добавляем префиксы для callback-данных
VB_CALLBACK_PREFIX = "vb_"  # vb = view_booking


class BookingBot:
    def __init__(self):
        self.token = Config.TELEGRAM_BOOKING_BOT_TOKEN
        self.allowed_usernames = [u.lower() for u in
                                  Config.ALLOWED_TELEGRAM_USERNAMES]
        self.application = None
        self.remote_web_app_url = Config.REMOTE_WEB_APP_URL
        self._telethon_initialized = False
        logger.info("BookingBot initialized")
        logger.info(f"Token: {self.token[:10]}...")
        logger.info(f"Allowed users: {self.allowed_usernames}")
        logger.info(f"Remote web app URL: {self.remote_web_app_url}")

    async def _ensure_telethon(self):
        """Ленивая инициализация Telethon клиента при первом использовании"""
        if self._telethon_initialized:
            return True

        try:
            from telega.telegram_client import telegram_client
            logger.info("🔄 Initializing Telethon client for BookingBot...")

            # Проверяем существование сессии
            if not await telegram_client.check_existing_session():
                logger.warning("⚠️ No existing session found, attempting to connect...")
                if not await telegram_client.ensure_connection():
                    logger.error("❌ Failed to initialize Telethon client")
                    return False

            # Загружаем кэш entity
            await telegram_client.preload_entity_cache()
            self._telethon_initialized = True
            logger.info("✅ Telethon client ready for BookingBot")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize Telethon client: {e}")
            return False

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
        # Создаем приложение с увеличенными таймаутами
        self.application = (
            Application.builder()
            .token(self.token)
            .connect_timeout(30.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .pool_timeout(30.0)
            .build()
        )

        # Сохраняем URL веб-приложения в bot_data для доступа из обработчиков
        self.application.bot_data['web_app_url'] = self.remote_web_app_url

        # 1. Обработчики команд с проверкой доступа
        self._add_secure_command_handler("start", start)
        self._add_secure_command_handler("help", help_command)
        self._add_secure_command_handler("view_booking", view_booking_handler)
        self._add_secure_command_handler("view_available_dates", view_dates_handler)
        self._add_secure_command_handler("calculation", calculation_command)
        self._add_secure_command_handler("sync_booking", sync_handler)
        self._add_secure_command_handler("exit", exit_bot)

        # 2. CallbackHandler для view_booking с фильтром по префиксу
        self._add_secure_callback_handler(
            view_booking_handler,
            pattern=f"^{VB_CALLBACK_PREFIX}.*"
        )

        # 3. Обработчики для меню расчета (только закрытие меню)
        self._add_secure_callback_handler(close_calculation_menu_handler, pattern="^close_calculation_menu$")

        # 4. Обработчик JSON из приватного канала (фоновая передача данных форм)
        if Config.TELEGRAM_DATA_CHANNEL_ID:
            json_filter = filters.Document.MimeType('application/json') | filters.Document.FileExtension('json')
            self.application.add_handler(
                MessageHandler(json_filter, self.handle_channel_document)
            )
            logger.info(f"✅ JSON form handler enabled for channel: {Config.TELEGRAM_DATA_CHANNEL_ID}")
        else:
            logger.warning("⚠️ TELEGRAM_DATA_CHANNEL_ID not set — form handler disabled")

        # 5. Обработчик неизвестных команд
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

    async def debug_all_messages(self, update: Update, context):
        chat = update.effective_chat
        logger.info(f"📩 [DEBUG] Получено сообщение из чата: {chat.id} ({chat.title or chat.username})")
        if update.message and update.message.document:
            logger.info(f"📄 Документ: {update.message.document.file_name}")

    async def handle_channel_document(self, update: Update, context):
        """
        Обработчик JSON-документов из приватного канала.
        Поддерживает как группы (update.message), так и каналы (update.channel_post).
        """
        logger.info("🔍 handle_channel_document: метод ВЫЗВАН")

        if not update:
            logger.warning("⚠️ update is None")
            return

        # Определяем источник сообщения
        message = update.message or update.channel_post
        if not message:
            logger.warning("⚠️ Ни update.message, ни update.channel_post не найдены")
            logger.debug(f"Содержимое update: {update}")
            return

        chat = message.chat
        channel_id = Config.TELEGRAM_DATA_CHANNEL_ID

        logger.info(f"📥 Получено сообщение в чате: {chat.id} ({chat.title or 'no title'})")

        if not channel_id:
            logger.error("❌ TELEGRAM_DATA_CHANNEL_ID не задан")
            return

        if str(chat.id) != channel_id:
            logger.info(f"⏭️ Сообщение из чата {chat.id} проигнорировано (ожидался {channel_id})")
            return

        if not message.document:
            logger.info("⏭️ Сообщение не содержит документа")
            return

        doc = message.document
        file_name = doc.file_name or "unnamed.json"
        mime_type = doc.mime_type or "unknown"

        logger.info(f"📂 Имя файла: {file_name}")
        logger.info(f".mime_type: {mime_type}")

        if not (mime_type == 'application/json' or file_name.lower().endswith('.json')):
            logger.info(f"⏭️ Файл '{file_name}' не является JSON")
            return

        base_name = file_name.rsplit('.', 1)[0]
        base_name_lower = base_name.lower()

        # Карта префиксов → обработчиков
        handlers_map = {
            "договор": ("main_tg_bot.handlers.contract_handler", "handle_contract"),
            "удаление_бронь": ("main_tg_bot.handlers.delete_booking_handler", "handle_delete_booking"),
            "изменение_бронь": ("main_tg_bot.handlers.edit_booking_handler", "handle_edit_booking"),
            "бронь": ("main_tg_bot.handlers.add_booking_handler", "handle_add_booking"),
            "рассылка": ("main_tg_bot.handlers.telegram_poster_handler", "handle_telegram_poster"),
        }

        # Определяем, какой обработчик подходит
        handler_func = None
        matched_prefix = None

        for prefix, (module_path, func_name) in handlers_map.items():
            if base_name_lower.startswith(prefix.lower()):
                try:
                    module = __import__(module_path, fromlist=[func_name])
                    handler_func = getattr(module, func_name)
                    matched_prefix = prefix
                    break
                except (ImportError, AttributeError) as e:
                    logger.error(f"❌ Не удалось загрузить обработчик для '{prefix}': {e}")
                    return

        if handler_func is None:
            logger.warning(f"❓ Неизвестный префикс в имени файла: '{base_name}' — игнорируем")
            return

        logger.info(f"🏷️ Префикс обработчика: '{matched_prefix}'")

        try:
            logger.info("⬇️ Загрузка файла...")
            file = await doc.get_file()
            file_bytes = await file.download_as_bytearray()
            json_content = file_bytes.decode('utf-8')
            data = json.loads(json_content)
            logger.info("✅ JSON успешно загружен и распарсен")
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке/парсинге '{file_name}': {e}")
            return

        try:
            # Убеждаемся, что Telethon клиент инициализирован для обработки
            await self._ensure_telethon()
            await handler_func(data, file_name)
            logger.info(f"✅ Обработка файла '{file_name}' завершена")
        except Exception as e:
            logger.error(f"💥 Ошибка в обработчике '{matched_prefix}' для '{file_name}': {e}", exc_info=True)

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

            self.setup_handlers()

            logger.info("Starting bot polling...")
            print("=" * 50)
            print("🤖 Бот запущен!")
            print(f"🌐 Удаленный сервер форм: {self.remote_web_app_url}")
            print("📋 Доступные команды:")
            for cmd, desc in COMMANDS:
                print(f"   /{cmd} - {desc}")
            print("=" * 50)

            # Запускаем бота - Telethon клиент будет инициализирован лениво
            self.application.run_polling(drop_pending_updates=True)

        except Exception as e:
            logger.error(f"Bot crashed: {e}", exc_info=True)
            raise


def sync_google_sheets():
    """Выполняет синхронизацию всех листов Google Sheets с локальными CSV."""
    try:
        sync_manager = GoogleSheetsCSVSync()
        logger.info("Starting full Google Sheets sync...")
        results = sync_manager.sync_all_sheets("csv_to_google")
        success_count = sum(results.values())
        total_count = len(results)
        logger.info(f"Sync completed: {success_count}/{total_count} sheets successful")
        print(f"✅ Синхронизация завершена: {success_count}/{total_count} листов")
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
        logger.info("Starting bot initialization...")
        # НЕ инициализируем Telethon здесь - он будет инициализирован лениво
        # при первом использовании через send_tg_reklama

        bot = BookingBot()
        bot.run()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)