import requests
import time
import logging
import os
from dotenv import load_dotenv
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")

load_dotenv()

AVITO_CLIENT_ID = os.getenv('AVITO_CLIENT_ID')
AVITO_CLIENT_SECRET = os.getenv('AVITO_CLIENT_SECRET')
AVITO_TOKEN_URL = os.getenv('AVITO_TOKEN_URL')
AVITO_REFRESH_TOKEN_URL = os.getenv('AVITO_REFRESH_TOKEN_URL')

# Функция для получения токена
def get_token():
    payload = {
        'grant_type': 'client_credentials',
        'client_id': AVITO_CLIENT_ID,
        'client_secret': AVITO_CLIENT_SECRET
    }
    response = requests.post(AVITO_TOKEN_URL, data=payload)
    logging.debug(f"get_token {response.text}")
    response.raise_for_status()
    return response.json()

# Функция для обновления токена
def refresh_token(refresh_token):
    payload = {
        'grant_type': 'refresh_token',
        'client_id': AVITO_CLIENT_ID,
        'client_secret': AVITO_CLIENT_SECRET,
        'refresh_token': refresh_token
    }
    response = requests.post(AVITO_REFRESH_TOKEN_URL, data=payload)
    logging.debug(f"refresh_token {response.text}")
    response.raise_for_status()
    return response.json()

# Пример использования
def avito_token():
    # Получаем токен
    token_data = get_token()
    access_token = token_data['access_token']
    refresh_token = token_data['access_token']
    expires_in = token_data['expires_in']
    token_expiry_time = time.time() + expires_in

    # Проверяем, истекло ли время жизни токена
    if time.time() > token_expiry_time:
        print("Токен истек, обновляем...")
        token_data = refresh_token(refresh_token)
        access_token = token_data['access_token']
        refresh_token = token_data['refresh_token']
        expires_in = token_data['expires_in']
        token_expiry_time = time.time() + expires_in
        logging.info(f"Токен обновлен")
    else:
        logging.info(f"Токен действителен")
    logging.info(f"avito_token = {avito_token}")
    return access_token

    # Теперь можно использовать access_token для запросов к API Avito
    # Теперь можно использовать access_token для запросов к API Avito
    # headers = {
    #    'Authorization': f'Bearer {access_token}',
    #    'Content-Type': 'application/json'
    # }

    # Пример запроса к API Avito
    # response = requests.get('https://api.avito.ru/ваш_эндпоинт', headers=headers)
    # print(response.json())

