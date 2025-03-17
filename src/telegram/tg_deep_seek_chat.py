import logging
import os
from os import system

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")

from telethon import TelegramClient, events

# Ваши данные от my.telegram.org
API_ID = ''
API_HASH = ''

# Имя сессии (может быть любым)
SESSION_NAME = 'my_session'

# Создаем клиент
client = TelegramClient('mybot',SESSION_NAME, API_ID, API_HASH, system_version='4.16.30-vxCUSTOM')

# Запускаем клиент
client.start()

# Функция для отправки сообщения боту и получения ответа
async def send_message_to_bot():
    print(f"Ответ от бота: ")
    # Укажите username бота (например, @BotFather)
#    bot_username = '@Qwen_Telegram_bot'

    # Отправляем сообщение боту
#    await client.send_message(bot_username, '/start')

    # Ждем ответа от бота
#    @client.on(events.NewMessage(from_users=bot_username))
#    async def handler(event):
#        print(f"Ответ от бота: {event.text}")
#        await event.reply('Спасибо за ответ!')

    # Запускаем прослушивание новых сообщений
#    await client.run_until_disconnected()

# Запускаем функцию
#with client:
#    client.loop.run_until_complete(send_message_to_bot())