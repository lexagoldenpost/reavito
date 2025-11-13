# send_bookings.py
from datetime import datetime

from common.database import SessionLocal
from sqlalchemy import select, or_, and_, func, case
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from common.logging_config import setup_logger
from new_halo_notification_service import send_to_specific_chat
from old.sync_db_google_sheets.channel_monitor import AsyncSessionLocal
from old.sync_db_google_sheets.models import Chat

logger = setup_logger("send_bookings")

# Добавляем префиксы для callback-данных
CALLBACK_PREFIX = "sb_"  # sb = send_bookings
SEND_TO_CHAT = f"{CALLBACK_PREFIX}send_to"
REFRESH_CHATS = f"{CALLBACK_PREFIX}refresh"


async def send_bookings_handler(update, context):
  """Обработчик для рассылки бронирований"""
  logger.info("Entered send_bookings_handler")
  try:
    if update.callback_query:
      logger.debug(f"Received callback query: {update.callback_query.data}")
      # Проверяем, что callback относится к этому модулю
      if update.callback_query.data.startswith(CALLBACK_PREFIX):
        logger.debug("Callback belongs to this module, processing...")
        return await handle_callback(update, context)
      else:
        logger.debug("Callback not for this module, skipping...")
        # Пропускаем callback, если он не для этого модуля
        return
    elif update.message:
      logger.debug(f"Received message: {update.message.text}")
      return await handle_message(update, context)
    else:
      logger.error("Unknown update type in send_bookings_handler")

  except Exception as e:
    logger.error(f"Error in send_bookings_handler: {e}", exc_info=True)
    error_message = "Произошла ошибка при обработке запроса"
    if hasattr(context, 'user_data'):
      context.user_data['step'] = 1  # Сбрасываем step при ошибке
    await send_reply(update, error_message)


async def handle_message(update, context):
  if update.message.text.strip().lower() == '/exit':
    if hasattr(context, 'user_data'):
      context.user_data.clear()
    await send_reply(update, "Сессия завершена. Начните заново.")
    return

  if not hasattr(context, 'user_data') or 'step' not in context.user_data:
    await show_available_chats(update, context)
    context.user_data['step'] = 1


async def handle_callback(update, context):
  """Обработка нажатия на кнопку"""
  logger.info("Entered handle_callback")
  query = update.callback_query
  await query.answer()
  logger.debug(f"Callback query answered: {query.data}")

  try:
    if query.data.startswith(
        SEND_TO_CHAT):  # Проверяем конкретный префикс для действий
      logger.info(f"Processing SEND_TO_CHAT action: {query.data}")
      # Извлекаем chat_name из callback_data (формат: "sb_send_to_STR")
      logger.debug(f"Extracting chat_name from {query.data}")
      parts = query.data.split('_')
      if len(parts) >= 3:
        chat_name = '_'.join(parts[
                             3:])  # Объединяем оставшиеся части на случай если chat_name содержит _
        logger.info(f"Preparing to send notification to chat_name: {chat_name}")
        await send_notification_to_chat(update, context, chat_name)
      else:
        logger.error(f"Invalid callback_data format: {query.data}")
        if hasattr(context, 'user_data'):
          context.user_data['step'] = 1  # Сбрасываем step при ошибке
        await send_reply(update,
                         "Ошибка: неверный формат запроса \nВыход /exit")
    elif query.data == REFRESH_CHATS:
      logger.info("Processing REFRESH_CHATS action")
      await show_available_chats(update, context)
    else:
      logger.debug(f"Ignoring callback with data: {query.data}")
      # Если callback не относится к этому модулю, пропускаем
      return
  except Exception as e:
    logger.error(f"Error in handle_callback: {e}", exc_info=True)
    await send_reply(update, "❌ Ошибка. Используйте /exit для сброса.")
    if hasattr(context, 'user_data'):
      context.user_data.clear()
  finally:
    try:
      logger.debug("Attempting to delete callback message")
      await query.message.delete()
      logger.debug("Callback message deleted successfully")
    except Exception as e:
      logger.warning(f"Could not delete message: {e}")


async def show_available_chats(update, context):
  """Показать доступные для рассылки чаты (async version)"""
  logger.info("Entered show_available_chats")
  try:
    logger.debug("Creating async session")
    async with AsyncSessionLocal() as session:  # Changed to async session
      current_date = datetime.now()
      logger.debug(f"Current date: {current_date}")

      days_since_last_send = case(
          (Chat.last_send == None, 9999),
          else_=func.extract('day', current_date - Chat.last_send)
      )
      logger.debug("Created days_since_last_send case expression")

      stmt = select(Chat).where(
          or_(
              Chat.last_send == None,
              and_(
                  Chat.send_frequency != None,
                  days_since_last_send > Chat.send_frequency
              )
          )
      ).order_by(Chat.chat_name)

      logger.debug(f"Executing query: {stmt}")
      result = await session.execute(stmt)  # Changed to async execute
      available_chats = result.scalars().all()
      logger.debug(f"Found {len(available_chats)} available chats")

      if not available_chats:
        logger.info("No available chats found")
        if hasattr(context, 'user_data'):
          context.user_data['step'] = 1  # Сбрасываем step при отсутствии чатов
        await send_reply(update,
                         "Нет чатов, доступных для рассылки в данный момент \nВыход /exit")
        return

      keyboard = []
      for chat in available_chats:
        display_name = chat.channel_name if chat.channel_name else chat.chat_name
        chat_info = f"{display_name}"

        if chat.chat_object:
          chat_info += f" ({chat.chat_object})"

        if chat.last_send:
          last_send_str = chat.last_send.strftime("%d.%m.%Y")
          days_passed = (current_date - chat.last_send).days
          chat_info += f"\nПоследняя: {last_send_str} ({days_passed} дн. назад)"
        else:
          chat_info += "\nРассылка не производилась"

        if chat.send_frequency:
          chat_info += f" | Частота: {chat.send_frequency} дн."

        logger.debug(
          f"Creating button for chat: {chat_info}, {SEND_TO_CHAT}_{chat.chat_name}")
        button = InlineKeyboardButton(
            text=chat_info,
            callback_data=f"{SEND_TO_CHAT}_{chat.chat_name}"
            # Используем chat_name вместо id
        )
        keyboard.append([button])

      refresh_button = InlineKeyboardButton("🔄 Обновить список",
                                            callback_data=REFRESH_CHATS)
      keyboard.append([refresh_button])
      logger.debug("Created all buttons for keyboard")

      reply_markup = InlineKeyboardMarkup(keyboard)
      await send_reply(
          update,
          "Выберите чат для рассылки:",
          reply_markup=reply_markup
      )
      logger.info("Successfully showed available chats")

  except Exception as e:
    logger.error(f"Error in show_available_chats: {e}", exc_info=True)
    if hasattr(context, 'user_data'):
      context.user_data['step'] = 1  # Сбрасываем step при ошибке
    await send_reply(update, "Ошибка при получении списка чатов \nВыход /exit")


async def send_notification_to_chat(update, context, chat_name):
  """Отправка уведомления в конкретный чат"""
  logger.info(f"Entered send_notification_to_chat for chat_name: {chat_name}")
  try:
    logger.debug("Creating sync session")
    with SessionLocal() as session:
      logger.debug(f"Getting chat with name: {chat_name}")
      # Ищем чат по chat_name вместо id
      chat = session.execute(
          select(Chat).where(Chat.chat_name == chat_name)
      ).scalar_one_or_none()

      if not chat:
        logger.error(f"Chat not found in database: {chat_name}")
        await send_reply(update, "❌ Чат не найден. Выход /exit")
        if hasattr(context, 'user_data'):
          context.user_data.clear()  # Полностью очищаем user_data
        return

      display_name = chat.channel_name if chat.channel_name else chat.chat_name
      title = chat.chat_object if chat.chat_object else "HALO Title"

      logger.info(
          f"Sending announcement to chat {chat.chat_name} with object {title}")
      success = await send_to_specific_chat(
          chat_id=chat.chat_name,
          title=title
          # Removed the dry_run parameter
      )

      if success:
        logger.debug("Notification sent successfully, updating last_send")
        chat.last_send = datetime.now()
        session.commit()
        logger.debug("Database updated successfully")

        await send_reply(
            update,
            f"✅ Рассылка успешно отправлена в:\n"
            f"Название: {display_name}\n"
            f"Объект: {chat.chat_object or 'не указан'}\n"
            f"ID чата: {chat.chat_name}"
        )
        logger.info("Success notification sent to user")
        if hasattr(context, 'user_data'):
          context.user_data.clear()  # Сбрасываем состояние
      else:
        logger.error(f"Failed to send notification to chat {chat.chat_name}")
        if hasattr(context, 'user_data'):
          context.user_data['step'] = 1  # Сбрасываем step при ошибке
        await send_reply(
            update,
            f"❌ Ошибка при отправке рассылки в {display_name} \nВыход /exit"
        )

  except Exception as e:
    logger.error(f"Error in send_notification_to_chat: {e}", exc_info=True)
    await send_reply(update, "❌ Критическая ошибка. Сессия сброшена. /exit")
    if hasattr(context, 'user_data'):
      context.user_data.clear()  # Принудительный сброс

async def send_reply(update, text, reply_markup=None, parse_mode=None):
  """Универсальная функция отправки сообщения"""
  logger.debug(f"Preparing to send reply with text: {text}")
  try:
    if update.callback_query:
      logger.debug("Sending reply to callback_query")
      await update.callback_query.message.reply_text(
          text,
          reply_markup=reply_markup,
          parse_mode=parse_mode
      )
    elif update.message:
      logger.debug("Sending reply to message")
      await update.message.reply_text(
          text,
          reply_markup=reply_markup,
          parse_mode=parse_mode
      )
    logger.debug("Reply sent successfully")
  except Exception as e:
    logger.error(f"Error in send_reply: {e}", exc_info=True)
    raise