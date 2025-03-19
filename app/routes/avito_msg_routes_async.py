from ..services.avito_message_in import create_avito_in, get_avito_msg
from flask import current_app

def background_task(data, headers):
    # Получаем подпись из заголовка
    signature = headers.get('x-avito-messenger-signature')
    if not signature:
        current_app.logger.error("Signature missing...")
        return

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
    current_app.logger.debug(f"Received webhook data {data}")

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
            msg_id = data['payload']['value']['id']
            chat_id = data['payload']['value']['chat_id']
            content = data['payload']['value']['content']['text']
            item_id = data['payload']['value']['item_id']
            author_id = data['payload']['value']['author_id']
            avito_user_id = data['payload']['value']['user_id']
            create_avito_in(msg_id, chat_id, item_id, author_id, avito_user_id, content)
            current_app.logger.debug(f"New message from avito_msg {msg_id}")
    else:
        current_app.logger.debug(f"Нет данных для записи в БД")

        # Данные для вставки
        # new_msg = {
        #    'chat_id': chat_id,
        #    'item_id': item_id,
        #    'author_id': author_id,
        #    'content': content,
        #    'is_send_ii': True
        # }
        # sav_db(new_msg)