from ..models.avito_msg import Avito_Msg
from ..database import db
import time
from sqlalchemy.dialects.postgresql import insert
from flask import current_app

def long_running_task(task_id):
    """
    Длительная задача, которая выполняется в фоновом режиме.
    """
    print(f"Task {task_id} started.")
    time.sleep(10)  # Имитация длительной задачи
    print(f"Task {task_id} completed.")

def create_avito_in(data, headers):
    # Получаем подпись из заголовка
    current_app.logger.info(f"background_task start...{data}, {headers}")
    signature = headers.get('x-avito-messenger-signature')
    #if not signature:
     #   current_app.logger.error("Signature missing...")
      #  return
    current_app.logger.debug(f"Received webhook data {data}")
    # Пример обработки сообщения
    if data['payload']['type'] == 'message':
        if data['payload']['value']['chat_type'] == 'u2i' and \
            data['payload']['value']['author_id'] != 81743640 and (
            data['payload']['value']['item_id'] == 4341979279 or
            data['payload']['value']['item_id'] == 4118352589):
            msg_id = data['payload']['value']['id']
            chat_id = data['payload']['value']['chat_id']
            content = data['payload']['value']['content']['text']
            item_id = data['payload']['value']['item_id']
            author_id = data['payload']['value']['author_id']
            avito_user_id = data['payload']['value']['user_id']
            create_avito_in(msg_id, chat_id, item_id, author_id, avito_user_id, content)
            current_app.logger.debug(f"New message from avito_msg {msg_id}")

            stmt = insert(Avito_Msg).values(msg_id=msg_id,
                chat_id=chat_id,
                item_id=item_id,
                author_id=author_id,
                avito_user_id=avito_user_id,
                content=content,
                is_send_ii=True).on_conflict_do_nothing(
                index_elements=['msg_id'])
            db.session.execute(stmt)
            db.session.commit()
            current_app.logger.info(f"Новое сообщение добавлено в таблицу")
        else:
            current_app.logger.debug(f"Нет данных для записи в БД")

    else:
        current_app.logger.debug(f"Нет данных для записи в БД")


def get_avito_msg(id):
    return Avito_Msg.query.get(id)