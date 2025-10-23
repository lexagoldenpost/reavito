from datetime import datetime

import psycopg2
from apscheduler.schedulers.blocking import BlockingScheduler
from telethon.sync import TelegramClient

# Данные из https://my.telegram.org
api_id = ''  # Замените на ваш API ID
api_hash = ''  # Замените на ваш API Hash

# Настройки базы данных
# Configuration
db_config = {
  "database": "",
  "user": "",
  "password": "",
  "host": "localhost",
  'port': 5432
}

# Инициализация клиента Telethon
client = TelegramClient('LapkaAvitoBotTest', api_id, api_hash, system_version='4.16.30-vxCUSTOM')

# Функция для чтения из БД и отправки сообщений
def send_messages_from_db():
    # Подключение к PostgreSQL
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    try:
        # Выполняем запрос к базе данных
        cursor.execute("SELECT msg_id, content FROM avito_messages WHERE sent = FALSE")  # Пример запроса
        rows = cursor.fetchall()

        # Если сообщений нет, завершаем выполнение
        if not rows:
            print(f"{datetime.now()}: Сообщений для отправки нет.")
            return

        # Вход в аккаунт Telegram
        client.start(phone='')  # Укажите ваш номер телефона

        # Укажите username бота (например, @MyBot)
        bot_username = '@Bo'  # Замените на username бота

        # Отправка сообщений из базы данных
        for row in rows:
            msg_id, message_text = row  # Извлекаем данные из строки

            try:
                # Отправляем сообщение боту с таймаутом
                with client:
                    # Отправка сообщения
                    client.send_message(bot_username, message_text)
                    print(f"{datetime.now()}: Сообщение отправлено: {message_text}")

                    # Получение ответа от бота с таймаутом (например, 10 секунд)
                    response = client.get_messages(bot_username, limit=1, wait_time=10)
                    if response:
                        print(f"{datetime.now()}: Ответ от бота: {response[0].text}")
                    else:
                        print(f"{datetime.now()}: Бот не ответил в течение таймаута.")

                # Помечаем сообщение как отправленное (если нужно)
                cursor.execute("UPDATE avito_messages SET sent = TRUE WHERE msg_id = %s", (msg_id,))
                conn.commit()

            except Exception as e:
                print(f"{datetime.now()}: Ошибка при отправке сообщения: {e}")

    except Exception as e:
        print(f"{datetime.now()}: Ошибка: {e}")
    finally:
        # Закрываем соединение с базой данных
        cursor.close()
        conn.close()

# Настройка планировщика
scheduler = BlockingScheduler()

# Запуск задачи каждые 5 минут
scheduler.add_job(send_messages_from_db, 'interval', seconds=10)

# Основной блок
if __name__ == "__main__":
    # Запуск планировщика
    print(f"{datetime.now()}: Планировщик запущен. Ожидание задач...")
    scheduler.start()