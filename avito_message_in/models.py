from sqlalchemy import Column, Integer, String, Index, Boolean
from common.database import Base

class Message(Base):
    """
    Модель для хранения сообщений, полученных от вебхука Авито.
    """
    __tablename__ = "avito_messages"

    msg_id = Column(String, primary_key=True, index=True)            # ID сообщения
    created = Column(Integer, nullable=False)            # время создания
    chat_id = Column(String, nullable=False)          # ID чата
    content = Column(String, nullable=False)          # Текст сообщения
    item_id = Column(String, nullable=False)         # ID товара
    author_id = Column(String, nullable=False)       # ID автора сообщения
    user_id = Column(String, nullable=False)   # ID пользователя Авито
    sent = Column(Boolean, default=False)              # Флаг, указывающий, было ли сообщение отправлено в Telegram

    # Индекс для ускорения поиска по полю `chat_id`
    __table_args__ = (
        Index("idx_chat_id", chat_id),
    )

    def __repr__(self):
        return f"<Message(msg_id={self.msg_id}, chat_id={self.chat_id}, content={self.content}, item_id={self.item_id}, author_id={self.author_id}, user_id={self.user_id})>"