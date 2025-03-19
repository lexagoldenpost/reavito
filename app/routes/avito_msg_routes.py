from flask import Blueprint, request, jsonify
from ..services.avito_message_in import create_avito_in, get_avito_msg
from flask import current_app
from ..routes.avito_msg_routes_async import background_task
import asyncio

avito_msg_bp = Blueprint('avito_msg', __name__)

@avito_msg_bp.route('/new_message', methods=['POST'])
def add_avito_msg():
    # Получаем данные и заголовки из запроса
    request_data = request.json  # Данные из тела запроса
    headers = dict(request.headers)  # Заголовки запроса
    # Запуск асинхронной задачи
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_in_executor(None, lambda: loop.run_until_complete(background_task(request_data, headers)))
    #current_app.logger.info("Initializing database...")
    return jsonify({"ok": True}), 200

@avito_msg_bp.route('/<int:id>', methods=['GET'])
def fetch_avito_msg(id):
    avito_msg = get_avito_msg(id)
    if avito_msg:
        return jsonify({"id": avito_msg.id, "name": avito_msg.name})
    else:
        return jsonify({"error": "User not found"}), 404