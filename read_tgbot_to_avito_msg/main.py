import requests
from common.database import SessionLocal
from common.logging_config import setup_logger
from common.config import Config

logger = setup_logger("service3")

def send_to_avito(message):
    url = "https://api.avito.ru/messages"
    headers = {
        "Authorization": f"Bearer {Config.AVITO_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": message
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def process_message(message):
    send_to_avito(message)
    logger.info(f"Сообщение отправлено в Авито: {message}")

if __name__ == "__main__":
    # Здесь можно добавить логику для чтения сообщений от Telegram
    process_message("Пример сообщения")