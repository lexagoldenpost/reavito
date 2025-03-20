from telethon import TelegramClient

# Данные из https://my.telegram.org
TELEGRAM_API_ID = '23820502'
TELEGRAM_API_HASH = '69ebf99b272aaa183a2821a3271e04de'

# Инициализация клиента
client = TelegramClient('session_name', TELEGRAM_API_ID, TELEGRAM_API_HASH, system_version='4.16.30-vxCUSTOM')

async def send_message_as_user():
    # Вход в аккаунт
    await client.start(phone='+79162000307')

    # Отправка сообщения
    await client.send_message('@LapkaAvitoBot', 'Привет, это сообщение от пользователя!')

# Запуск клиента
with client:
    client.loop.run_until_complete(send_message_as_user())