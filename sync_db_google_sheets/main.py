# main.py
from telegram.ext import (
  Application,
  CommandHandler,
  MessageHandler,
  filters,
  CallbackQueryHandler
)

from add_booking import AddBookingHandler
from chat_sync import process_chats_sheet
from commands import (
  COMMANDS,
  start,
  help_command,
  view_booking_handler,
  view_dates_handler,
  sync_handler,
  exit_bot,
  edit_booking_conv_handler  # Добавьте этот импорт
)
from common.config import Config
from common.logging_config import setup_logger
from create_contract import get_contract_conversation_handler
from sync_db_google_sheets.send_bookings import send_bookings_handler
from sync_google_booking import process_google_sheets_to_db
from sync_task import process_notifications_sheet
from google_sheets_to_channels_keywords import process_channels_keywords_sheet

logger = setup_logger("main")


class BookingBot:
  def __init__(self):
    self.token = Config.TELEGRAM_BOOKING_BOT_TOKEN
    self.allowed_usernames = [u.lower() for u in
                              Config.ALLOWED_TELEGRAM_USERNAMES]
    self.application = None
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
      # Для callback-запросов используем edit_message_text
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

  def _add_secure_callback_handler(self, handler):
    """Добавляет обработчик callback с проверкой прав доступа"""
    wrapped_handler = lambda update, context: self._secure_handler_wrapper(
      handler, update, context)
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
    self._add_secure_command_handler("send_bookings", send_bookings_handler)
    self._add_secure_command_handler("exit", exit_bot)

    # 2. ConversationHandler для add_booking (проверка встроена в start_add_booking)
    booking_handler = AddBookingHandler(self)
    self.application.add_handler(booking_handler.get_conversation_handler())

    # 3. Добавляем обработчик редактирования бронирования
    self.application.add_handler(edit_booking_conv_handler)

    # 3. CallbackHandler для view_booking с проверкой доступа
    self._add_secure_callback_handler(view_booking_handler)

    # 4. Обработчик создания договора (проверка должна быть встроена в обработчик)
    self.application.add_handler(get_contract_conversation_handler())

    # 5. Обработчик неизвестных команд (без проверки доступа)
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
    process_notifications_sheet()
    process_chats_sheet()
    process_channels_keywords_sheet()
    logger.info("Starting bot initialization...")
    bot = BookingBot()
    bot.run()
  except Exception as e:
    logger.critical(f"Failed to start bot: {e}", exc_info=True)