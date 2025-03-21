import requests

# Замените на ваш токен доступа
ACCESS_TOKEN = ''
USER_ID = ''

# URL для запроса
url = f'https://api.avito.ru/messenger/v2/accounts/{USER_ID}/chats'

# Параметры запроса
params = {
    'item_ids': '4341979279,4118352589',  # Фильтр по item_ids
    'chat_types': 'u2i',  # Фильтр по chat_types
    'limit': 100,  # Максимальное количество чатов за один запрос
    'offset': 0  # Начальный сдвиг
}

# Заголовки запроса
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}

# Множество для хранения уникальных идентификаторов чатов
chat_ids = set()

# Флаг для остановки цикла
has_more_chats = True

while has_more_chats:
    # Выполнение GET-запроса
    response = requests.get(url, headers=headers, params=params)

    # Проверка статуса ответа
    if response.status_code == 200:
        chats = response.json()
        print(f"Получено {len(chats.get('chats', []))} чатов.")

        # Извлечение уникальных идентификаторов чатов
        for chat in chats.get('chats', []):
            chat_id = chat.get('id')
            if chat_id:
                chat_ids.add(chat_id)

        # Проверка, есть ли еще чаты
        if len(chats.get('chats', [])) < params['limit']:
            has_more_chats = False  # Если чатов меньше лимита, значит, это последняя страница
        else:
            params['offset'] += params['limit']  # Увеличиваем сдвиг для следующей страницы
    else:
        print(f"Ошибка при выполнении запроса: {response.status_code}")
        print(response.text)
        break

# Сохранение идентификаторов в файл
if chat_ids:
    with open('chat_ids.txt', 'w', encoding='utf-8') as file:
        for chat_id in chat_ids:
            file.write(f"{chat_id}\n")

    print(f"Уникальные идентификаторы чатов сохранены в файл 'chat_ids.txt'. Всего чатов: {len(chat_ids)}.")
else:
    print("Нет чатов для сохранения.")