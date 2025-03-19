from ..database import db

# 3. Определение модели таблицы
class Avito_Msg(db.Model):
    __tablename__ = 'avito_chat'
    msg_id = db.Column(db.String, primary_key=True)
    chat_id = db.Column(db.String)
    item_id = db.Column(db.String)
    author_id = db.Column(db.String)
    avito_user_id = db.Column(db.String)
    content = db.Column(db.String)
    is_send_ii = db.Column(db.Boolean)  # Поле для хранения JSON-данных

