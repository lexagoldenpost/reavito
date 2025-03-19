from flask import Blueprint, request, jsonify
from ..services.avito_message_in import create_avito_in, get_avito_msg
from flask import current_app
import asyncio

avito_msg_bp = Blueprint('avito_msg', __name__)

@avito_msg_bp.route('/new_message', methods=['POST'])
def add_avito_msg():
    # Получаем данные и заголовки из запроса
    request_data = request.json  # Данные из тела запроса
    headers = dict(request.headers)  # Заголовки запроса

    # Запуск асинхронной функции
    #loop = asyncio.new_event_loop()
    #asyncio.set_event_loop(loop)
    #loop.run_until_complete(create_avito_in(request_data, headers))
    #loop.close()
    create_avito_in(request_data, headers)

    #current_app.logger.info(f"Avito request...{request_data}")
    return jsonify({"ok": True}), 200

@avito_msg_bp.route('/<int:id>', methods=['GET'])
def fetch_avito_msg(id):
    avito_msg = get_avito_msg(id)
    if avito_msg:
        return jsonify({"id": avito_msg.id, "name": avito_msg.name})
    else:
        return jsonify({"error": "User not found"}), 404

def background_taskkk(data, headers):
    # Получаем подпись из заголовка
    current_app.logger.info(f"background_task start...{data}, {headers}")
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
