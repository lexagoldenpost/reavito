import requests
import logging
import os
from dotenv import load_dotenv
from src.avito.avito_auth import avito_token
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")

# Ваш токен доступа
ACCESS_TOKEN = avito_token()

# ID объявления, информацию о котором вы хотите получить
ITEM_ID = '4086382580'
AVITO_USER_ID = os.getenv('AVITO_USER_ID')

# URL для получения информации о объявлении

ITEM_URL = f'https://api.avito.ru/core/v1/accounts/{AVITO_USER_ID}/items/{ITEM_ID}/'


# Заголовки запроса
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}

# Функция для получения информации о объявлении
def get_item_info(item_id):
    response = requests.get(ITEM_URL, headers=headers)
    logging.debug(f"get_item_info {response.text}")
    response.raise_for_status()  # Проверка на ошибки
    return response.json()

# Пример использования
def get_avito_item():
    try:
        # Получаем информацию о объявлении
        item_info = get_item_info(ITEM_ID)
        print("Информация о объявлении:")
        print(item_info)
    except requests.exceptions.HTTPError as err:
        print(f"Ошибка при запросе: {err}")
    except Exception as e:
        print(f"Произошла ошибка: {e}")

