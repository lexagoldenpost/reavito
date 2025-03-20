import time
import requests
from common.database import SessionLocal
from common.logging_config import setup_logger
from common.config import Config
from service1.models import Message

logger = setup_logger("service2")

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, json=payload)
    return response.json()

def read_and_send():
    db = SessionLocal()
    try:
        messages = db.query(Message).filter(Message.sent == False).all()
        for message in messages:
            send_to_telegram(message.message)
            message.sent = True
            db.commit()
            logger.info(f"Сообщение отправлено в Telegram: {message.message}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    while True:
        read_and_send()
        time.sleep(60)  # Проверка каждую минуту