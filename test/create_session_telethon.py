import asyncio
from telethon import TelegramClient
from common.config import Config


async def create_session():
    client = TelegramClient(
        'lapka_send_booking_session_name',
        Config.TELEGRAM_API_SEND_BOOKING_ID,
        Config.TELEGRAM_API_SEND_BOOKING_HASH
    )

    await client.start(phone=Config.TELEGRAM_SEND_BOOKING_PHONE)
    print("Сессия создана успешно!")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(create_session())