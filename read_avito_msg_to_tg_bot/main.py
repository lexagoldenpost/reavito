from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import requests
from common.database import SessionLocal
from common.logging_config import setup_logger
from common.config import Config
from avito_message_in.models import Message
from telethon import TelegramClient
import asyncio

logger = setup_logger("read_avito_msg_to_tg_bot")

# Создаем клиент
client = TelegramClient('LapkaAvitoBotTest', Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH, system_version='4.16.30-vxCUSTOM')

# Не и мспользую
# def send_to_telegram(message):
#     url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
#     payload = {
#         "chat_id": Config.TELEGRAM_CHAT_ID,
#         "text": message
#     }
#     logger.info(f"Сообщение для в Telegram: {payload}")
#     response = requests.post(url, json=payload)
#     return response.json()

# Функция для чтения из БД и отправки сообщений
async def send_messages_from_db():
    db = SessionLocal()
    try:
        messages = db.query(Message).filter(Message.sent == False).all()
        # Если сообщений нет, завершаем выполнение
        if not messages:
            logger.info(f"{datetime.now()}: Сообщений для отправки нет.")
            return
        # Вход в аккаунт ТГ
        await client.start(phone=Config.TELEGRAM_PHONE)
        for message in messages:
            #send_to_telegram(message.content)
            # Отправляем сообщение боту
            await client.send_message(Config.TELEGRAM_BOT_NAME, message.content)
            message.sent = True
            db.commit()
            logger.info(f"Сообщение отправлено в Telegram: {message.content}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
    finally:
        db.close()

# Функция для запуска задачи по расписанию
def scheduled_task():
    # Создаем новый цикл событий для текущего потока
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Запускаем асинхронную задачу
    with client:
        loop.run_until_complete(send_messages_from_db())

if __name__ == "__main__":
    # Настройка планировщика
    scheduler = BlockingScheduler()
    # Запуск задачи каждые 5 минут
    scheduler.add_job(scheduled_task, 'interval', minutes=1)
    scheduler.start()
    # Запуск планировщика
    logger.info(f"{datetime.now()}: Планировщик запущен. Ожидание задач...")