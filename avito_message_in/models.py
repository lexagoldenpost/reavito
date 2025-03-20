from sqlalchemy import Column, Integer, String, Index
from common.database import Base

class Message(Base):
    """
    Модель для хранения сообщений, полученных от вебхука Авито.
    """
    __tablename__ = "avito_messages"

    msg_id = Column(String, primary_key=True, index=True)            # ID сообщения
    chat_id = Column(String, nullable=False)          # ID чата
    content = Column(String, nullable=False)          # Текст сообщения
    item_id = Column(String, nullable=False)         # ID товара
    author_id = Column(String, nullable=False)       # ID автора сообщения
    avito_user_id = Column(String, nullable=False)   # ID пользователя Авито

    # Индекс для ускорения поиска по полю `chat_id`
    __table_args__ = (
        Index("idx_chat_id", chat_id),
    )

    def __repr__(self):
        return f"<Message(msg_id={self.msg_id}, chat_id={self.chat_id}, content={self.content}, item_id={self.item_id}, author_id={self.author_id}, avito_user_id={self.avito_user_id})>"