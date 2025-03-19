from flask import Flask, request, jsonify
import hmac
import hashlib
import main

import threading
import asyncio
import time
from avito_save_db_msg import save_db
#logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")


app = Flask(__name__)

async def background_task2():
    # Имитация длительной асинхронной задачи
    await asyncio.sleep(5)
    main.logging.debug(f"Фоновая задача завершена")

def background_task(data, headers):
    # Получаем подпись из заголовка
    time.sleep(5)
    main.AVITO_SECRET
    main.logging.debug(f"Фоновая задача начата")
    signature = headers.get('x-avito-messenger-signature')
    if not signature:
        return jsonify({'error': 'Signature missing'}), 403

    # Получаем сырые данные для проверки подписи
    # raw_data = request.get_data()

    # Генерируем HMAC подпись
    # generated_signature = hmac.new(
    #   AVITO_SECRET.encode('utf-8'),
    #   raw_data,
    #   hashlib.sha256
    # ).hexdigest()

    # Сравниваем подписи
    # if not hmac.compare_digest(signature, generated_signature):
    #   return jsonify({'error': 'Invalid signature'}), 403

    # Если подпись верна, обрабатываем данные
    #data = request.json
    main.logging.debug(f"Received webhook data {data}")

    # проверка на обяъвления

    # Пример обработки сообщения
    if data['payload']['type'] == 'message':
        # avito_msg = # Создаем новый JSON на основе данных из исходного
        # avito_msg = {
        #    "message_id": data["payload"]["value"]["id"],
        #    "chat_id": data["payload"]["value"]["chat_id"],
        #    "user_id": data["payload"]["value"]["user_id"],
        #    "text": data["payload"]["value"]["content"]["text"],
        #    "published_at": data["payload"]["value"]["published_at"]
        # }
        # Преобразуем новый словарь в JSON-строку
        # new_json_str = json.dumps(new_json, indent=2, ensure_ascii=False)
        if data['payload']['value']['chat_type'] == 'u2i' and data['payload']['value']['author_id'] != 81743640 and (
                data['payload']['value']['item_id'] == 4341979279 or data['payload']['value']['item_id'] == 4118352589):
            chat_id = data['payload']['value']['chat_id']
            content = data['payload']['value']['content']['text']
            item_id = data['payload']['value']['item_id']
            author_id = data['payload']['value']['author_id']
            avito_user_id = data['payload']['value']['user_id']
            save_db(chat_id, item_id, author_id, avito_user_id, content)
            main.logging.debug(f"New message from avito_msg {chat_id}")

        # Данные для вставки
        # new_msg = {
        #    'chat_id': chat_id,
        #    'item_id': item_id,
        #    'author_id': author_id,
        #    'content': content,
        #    'is_send_ii': True
        # }
        # sav_db(new_msg)

@app.route('/avito_webhook', methods=['POST'])
def handle_webhook():
    # Получаем данные и заголовки из запроса
    request_data = request.json  # Данные из тела запроса
    headers = dict(request.headers)  # Заголовки запроса
    # Запуск асинхронной задачи
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_in_executor(None, lambda: loop.run_until_complete(background_task(request_data, headers)))
    # Запуск фоновой задачи в отдельном потоке
    #thread = threading.Thread(target=background_task2())
    #thread.start()

    # Немедленный ответ клиенту
    # Отвечаем Avito, что запрос успешно обработан
    # Создаем JSON-ответ с ключом "key" и значением True
    response = {
        "ok": True
    }
    main.logging.debug(f"response {response}")
    return jsonify(response), 200
    #return jsonify({'ok': 'true'}), 200

if __name__ == '__main__':
  #app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')  # Для теста используем самоподписанный сертификат

  app.run(host='127.0.0.1', port=5000)  # Для теста используем самоподписанный сертификат
  main.logging.info(f"Старт")