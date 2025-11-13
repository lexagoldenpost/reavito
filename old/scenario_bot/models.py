import datetime

from common.database import Base
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy import TIMESTAMP


class Message_Scenario(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    msg_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=False)
    question = Column(String, nullable=False)
    response = Column(String, nullable=False)
    sent = Column(Boolean, default=False)
    created = Column(TIMESTAMP, default=datetime.datetime.now().time())