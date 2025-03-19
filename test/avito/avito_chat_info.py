import requests
import logging
import os
from dotenv import load_dotenv
from src.avito.avito_auth import avito_token
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")

# Ваш токен доступа
ACCESS_TOKEN = avito_token()


# ID чата, информацию о котором вы хотите получить
CHAT_ID = 'u2i-N0yDM0DbA2u0DJ9SzVHzcg'  # Замените на реальный ID чата
AVITO_USER_ID = os.getenv('AVITO_USER_ID')
AVITO_CHAT_URL = os.getenv('AVITO_CHAT_URL')
AVITO_MESSENGER_URL = os.getenv('AVITO_MESSENGER_URL')

# URL для получения информации о чате
CHAT_URL = f'{AVITO_CHAT_URL}{AVITO_USER_ID}/chats/{CHAT_ID}'

# Заголовки запроса
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}

# Функция для получения информации о чате
def get_chat_info(chat_id):
    try:
        response = requests.get(CHAT_URL, headers=headers)
        response.raise_for_status()  # Проверка на ошибки
        return response.json()
    except requests.exceptions.HTTPError as err:
        print(f"Ошибка при запросе: {err}")
        return None

# Функция для получения сообщений из чата
def get_chat_messages(chat_id):
    try:
        MESSENGER_URL = f'{AVITO_MESSENGER_URL}{AVITO_USER_ID}/chats/{CHAT_ID}/messages/'
        response = requests.get(MESSENGER_URL, headers=headers)
        response.raise_for_status()  # Проверка на ошибки
        return response.json()
    except requests.exceptions.HTTPError as err:
        print(f"Ошибка при запросе: {err}")
        return None

# Пример использования
def avito_chat_messages():
    # Получаем информацию о чате
    chat_info = get_chat_info(CHAT_ID)
    if chat_info:
        print("Информация о чате:")
        print(f"ID чата: {chat_info.get('id')}")
        print(f"Создан: {chat_info.get('created')}")
        print(f"Обновлен: {chat_info.get('updated')}")
        print(f"Пользователи: {[user['name'] for user in chat_info.get('users', [])]}")
        print("-" * 40)

        # Получаем сообщения из чата
        messages = get_chat_messages(CHAT_ID)
        if messages:
            print(f"Сообщения из чата {CHAT_ID}:")
            for message in messages.get('messages', []):
                print(f"Автор: {message.get('author_id')}")
                print(f"Текст: {message.get('content', {}).get('text', 'Нет текста')}")
                print(f"Тип: {message.get('type')}")
                print(f"Дата: {message.get('created')}")
                print("-" * 40)
        else:
            print("Не удалось получить сообщения.")
    else:
        print("Не удалось получить информацию о чате.")
