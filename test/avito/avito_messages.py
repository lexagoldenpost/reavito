import requests
import logging
import os
from common.avito_auth import avito_token
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")

# Ваш токен доступа
ACCESS_TOKEN = avito_token()

# ID объявления, информацию о котором вы хотите получить
ITEM_ID = '4341979279, 4118352589'
AVITO_USER_ID = os.getenv('AVITO_USER_ID')
AVITO_LIST_MESSENGER_URL = os.getenv('AVITO_LIST_MESSENGER_URL')

# URL для получения информации о объявлении

CHATS_URL = f'{AVITO_LIST_MESSENGER_URL}{AVITO_USER_ID}/chats'


# Заголовки запроса
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}


# Функция для получения списка чатов в разрезе объявления
def get_chats(item_ids):
    try:
        # Параметры запроса для получения только непрочитанных чатов
        params = {
            'item_ids': item_ids,
            'unread_only': 'false',  # Получаем только непрочитанные чаты
            'limit': 10,
            'offset': 10
        }

        response = requests.get(CHATS_URL, headers=headers , params=params)
        response.raise_for_status()  # Проверка на ошибки
        return response.json()
    except requests.exceptions.HTTPError as err:
        print(f"Ошибка при запросе: {err}")
        return None

# Пример использования
def avito_chats():
    # Получаем список чатов
    chats = get_chats()
    if chats:
        print("Список чатов:")
        for data in chats.get('chats', []):
            # Извлечение данных
            chat_id = data["id"]
            created_at = data["created"]
            updated_at = data["updated"]

            # Информация о последнем сообщении
            last_message = data["last_message"]
            message_id = last_message["id"]
            message_type = last_message["type"]
            message_author_id = last_message["author_id"]
            message_created = last_message["created"]

            # Информация о пользователях
            users = data["users"]
            for user in users:
                print(f"Имя пользователя: {user['name']}")
                print(f"ID пользователя: {user['id']}")
                print(f"Аватар: {user['public_user_profile']['avatar']['default']}")
                print("-" * 40)

            # Информация о контексте (объявлении)
            context = data["context"]["value"]
            item_id = context["id"]
            item_title = context["title"]
            item_price = context["price_string"]
            item_url = context["url"]

            # Вывод информации
            print(f"ID чата: {chat_id}")
            print(f"Создан: {created_at}")
            print(f"Обновлен: {updated_at}")
            print(f"Последнее сообщение: {message_type} от пользователя {message_author_id}")
            print(f"Объявление: {item_title}, цена: {item_price}, ссылка: {item_url}")
    else:
        print("Не удалось получить список чатов.")
