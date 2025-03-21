from common.database import SessionLocal
from common.logging_config import setup_logger
from avito_message_in.models import Message
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
import time
from intent_bot.main import IntentBot

# Настройка логгера для микросервиса
logger = setup_logger("read_avito_msg_to_tg_bot")

# Путь к JSON-файлу с намерениями
INTENTS_FILE = "intents.json"

# Инициализация бота
bot = IntentBot(INTENTS_FILE)

# Функция для чтения из БД и отправки сообщений
def send_messages_from_db():
    # Создаем сессию
    db = SessionLocal()

    try:
        # Выполняем запрос к базе данных
        messages = db.query(Message).filter(Message.sent == False).order_by(Message.created).all()

        # Проверка, есть ли сообщения
        if not messages:
            logger.info(f"{datetime.now()}: Новых сообщений для обработки нет.")
            return

        # Обработка сообщений из базы данных
        for message in messages:
            logger.info(f"{datetime.now()}: Обработка сообщения: {message.content}")

            try:
                # Отправляем сообщение боту и ждем ответа
                response = bot.process_message(message.content)
                logger.info(f"{datetime.now()}: Ответ от бота: {response}")

                # Если ответ получен, помечаем сообщение как отправленное
                if response:
                    message.sent = True
                    db.commit()
                    logger.info(f"{datetime.now()}: Сообщение помечено как отправленное.")

            except Exception as e:
                logger.error(f"{datetime.now()}: Ошибка при обработке сообщения: {e}")
                # Если ответ не получен, ждем 1 минуту и продолжаем
                logger.info(f"{datetime.now()}: Ожидание 1 минуту перед следующей попыткой...")
                time.sleep(60)  # Ждем 1 минуту

    except Exception as e:
        logger.error(f"{datetime.now()}: Ошибка при выполнении запроса к базе данных: {e}")
    finally:
        # Закрываем сессию
        db.close()

# Функция для запуска задачи по расписанию
def scheduled_task():
    logger.info(f"{datetime.now()}: Запуск задачи по расписанию...")
    send_messages_from_db()

if __name__ == "__main__":
    # Настройка планировщика
    scheduler = BlockingScheduler()

    # Запуск задачи каждые 5 секунд
    scheduler.add_job(scheduled_task, 'interval', seconds=5)

    # Запуск планировщика
    logger.info(f"{datetime.now()}: Планировщик запущен. Ожидание задач...")
    scheduler.start()