# send_bookings.py
from datetime import datetime
from sqlalchemy import select, or_, and_, func, case
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from common.database import SessionLocal
from common.logging_config import setup_logger
from sync_db_google_sheets.models import Chat
from new_halo_notification_service import send_to_specific_chat

logger = setup_logger("send_bookings")


async def send_bookings_handler(update, context):
  """Обработчик для рассылки бронирований"""
  try:
    if update.callback_query:
      return await handle_callback(update, context)
    elif update.message:
      return await handle_message(update, context)
    else:
      logger.error("Unknown update type in send_bookings_handler")

  except Exception as e:
    logger.error(f"Error in send_bookings_handler: {e}")
    error_message = "Произошла ошибка при обработке запроса"
    await send_reply(update, error_message)


async def handle_message(update, context):
  """Обработка текстового сообщения"""
  if 'step' not in context.user_data:
    await show_available_chats(update, context)
    context.user_data['step'] = 1


async def handle_callback(update, context):
  """Обработка нажатия на кнопку"""
  query = update.callback_query
  await query.answer()

  if query.data.startswith('send_to_'):
    chat_id = int(query.data.split('_')[2])
    await send_notification_to_chat(update, context, chat_id)
  elif query.data == 'refresh_chats':
    await show_available_chats(update, context)

  try:
    await query.message.delete()
  except Exception as e:
    logger.warning(f"Could not delete message: {e}")


async def show_available_chats(update, context):
  """Показать доступные для рассылки чаты"""
  try:
    with SessionLocal() as session:
      current_date = datetime.now()

      # Подзапрос для вычисления дней с последней рассылки
      days_since_last_send = case(
          (Chat.last_send == None, 9999),
          else_=func.extract('day', current_date - Chat.last_send)
      )

      stmt = select(Chat).where(
          or_(
              Chat.last_send == None,
              and_(
                  Chat.send_frequency != None,
                  days_since_last_send > Chat.send_frequency
              )
          )
      ).order_by(Chat.chat_name)

      result = session.execute(stmt)
      available_chats = result.scalars().all()

      if not available_chats:
        await send_reply(update,
                         "Нет чатов, доступных для рассылки в данный момент \nВыход /exit")
        return

      keyboard = []
      for chat in available_chats:
        # Используем channel_name если есть, иначе chat_name
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

        button = InlineKeyboardButton(
            text=chat_info,
            callback_data=f"send_to_{chat.id}"
        )
        keyboard.append([button])

      keyboard.append([InlineKeyboardButton("🔄 Обновить список",
                                            callback_data="refresh_chats")])

      reply_markup = InlineKeyboardMarkup(keyboard)
      await send_reply(
          update,
          "Выберите чат для рассылки:",
          reply_markup=reply_markup
      )

  except Exception as e:
    logger.error(f"Error in show_available_chats: {e}")
    await send_reply(update, "Ошибка при получении списка чатов \nВыход /exit")

async def send_notification_to_chat(update, context, chat_id):
  """Отправка уведомления в конкретный чат"""
  try:
    with SessionLocal() as session:
      # Получаем информацию о чате
      chat = session.get(Chat, chat_id)
      if not chat:
        await send_reply(update, "Чат не найден в базе данных \nВыход /exit")
        return

      # Определяем название для вывода (channel_name или chat_name)
      display_name = chat.channel_name if chat.channel_name else chat.chat_name

      # Вызываем модуль рассылки (всегда передаем chat_name)
      success = await send_to_specific_chat(chat.id, chat.chat_name, "HALO Title", dry_run=True)

      if success:
        # Обновляем дату последней рассылки
        chat.last_send = datetime.now()
        session.commit()

        await send_reply(
            update,
            f"✅ Рассылка успешно отправлена в:\n"
            f"Название: {display_name}\n"
            f"Объект: {chat.chat_object or 'не указан'}\n"
            f"ID: {chat.id}"
        )
      else:
        await send_reply(
            update,
            f"❌ Ошибка при отправке рассылки в {display_name} \nВыход /exit"
        )

  except Exception as e:
    logger.error(f"Error in send_notification_to_chat: {e}")
    await send_reply(update, "Ошибка при отправке рассылки \nВыход /exit")

async def send_reply(update, text, reply_markup=None, parse_mode=None):
  """Универсальная функция отправки сообщения"""
  if update.callback_query:
    await update.callback_query.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
  elif update.message:
    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )