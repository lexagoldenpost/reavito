from ..models.avito_msg import Avito_Msg
from ..database import db
from sqlalchemy.dialects.postgresql import insert
from flask import current_app


def create_avito_in(msg_id, chat_id, item_id, author_id, avito_user_id, content):
    new_avito_msg = Avito_Msg(
        msg_id=msg_id,
        chat_id=chat_id,
        item_id=item_id,
        author_id=author_id,
        avito_user_id=avito_user_id,
        content=content,
        is_send_ii=True
    )
    stmt = insert(Avito_Msg).values(new_avito_msg).on_conflict_do_nothing(
        index_elements=['msg_id'])
    db.session.execute(stmt)
    db.session.add(new_avito_msg)
    db.session.commit()
    current_app.logger.info(f"Новое сообщение добавлено в таблицу")

def get_avito_msg(id):
    return Avito_Msg.query.get(id)