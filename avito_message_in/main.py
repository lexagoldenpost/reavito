from fastapi import FastAPI, HTTPException, status, Header, Request
from pydantic import BaseModel
from common.logging_config import setup_logger
from common.database import SessionLocal
from avito_message_in.models import Message
import asyncio
import uvicorn
from typing import Optional

# Инициализация FastAPI приложения
app = FastAPI()

# Настройка логгера для микросервиса 1
logger = setup_logger("avito_message_in")

# Модель для данных вебхука от Авито
class AvitoWebhook(BaseModel):
    id: str
    version: str
    timestamp: int
    payload: dict  # Используем dict, чтобы не усложнять модель

# Асинхронная функция для сохранения данных в БД
async def save_to_db(msg_id: str,created: int, chat_id: str, content: str, item_id: str, author_id: str, user_id: str):
    db = SessionLocal()
    try:
        # Проверяем, существует ли сообщение с таким же msg_id
        existing_message = db.query(Message).filter(Message.msg_id == msg_id).first()
        if existing_message:
            logger.info(f"Сообщение с msg_id={msg_id} уже существует. Игнорируем.")
            return

        # Создаем объект сообщения и сохраняем его в БД
        db_message = Message(
            msg_id=msg_id,
            created = created,
            chat_id=chat_id,
            content=content,
            item_id=item_id,
            author_id=author_id,
            user_id=user_id
        )
        db.add(db_message)
        db.commit()
        logger.info(f"Данные сохранены в БД: msg_id={msg_id}, chat_id={chat_id}, content={content}, item_id={item_id}, author_id={author_id}, user_id={user_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при сохранении данных: {e}")
    finally:
        db.close()

# Обработчик POST-запросов на /webhook
@app.post("/avito/webhook/new_message")
async def avito_webhook(
    request: Request,
    data: AvitoWebhook,
    x_avito_messenger_signature: Optional[str] = Header(None)
):
    # Сразу отвечаем "ok": true
    response = {"ok": True}

    # Асинхронно проверяем подпись и условия
    asyncio.create_task(process_webhook(data, x_avito_messenger_signature))

    return response

# Асинхронная функция для обработки вебхука
async def process_webhook(data: AvitoWebhook, signature: Optional[str]):
    # Проверяем наличие заголовка x-avito-messenger-signature
    if not signature:
        logger.warning("Заголовок x-avito-messenger-signature отсутствует. Сообщение проигнорировано.")
        return

    # Проверяем условие: chat_type == 'u2i' и author_id != 81743640 и item_id в списке [4341979279, 4118352589]
    payload_value = data.payload.get("value", {})
    chat_type = payload_value.get("chat_type")
    author_id = payload_value.get("author_id")
    item_id = payload_value.get("item_id")

    if not (chat_type == "u2i" and author_id != 81743640 and item_id in [4341979279, 4118352589]):
        logger.warning(f"Условие не выполнено. Сообщение проигнорировано: chat_type={chat_type}, author_id={author_id}, item_id={item_id}")
        return

    # Извлекаем данные из сообщения
    msg_id = payload_value.get("id")
    created = payload_value.get("created")
    chat_id = payload_value.get("chat_id")
    content = payload_value.get("content", {}).get("text")
    user_id = payload_value.get("user_id")

    # Сохраняем данные в БД, если они корректны и сообщение не дублируется
    if msg_id and created and chat_id and content and item_id and author_id and user_id:
        await save_to_db(msg_id, created, chat_id, content, item_id, author_id, user_id)
    else:
        logger.warning("Не удалось извлечь все необходимые данные из сообщения")

# Запуск FastAPI приложения
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)