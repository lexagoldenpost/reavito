from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP
from sqlalchemy import Column, Integer, String, Index, Boolean
from common.database import Base
import datetime

class Message_Scenario(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    msg_id = Column(Integer, nullable=False)
    question = Column(String, nullable=False)
    response = Column(String, nullable=False)
    sent = Column(Boolean, default=False)
    created = Column(TIMESTAMP, default=datetime.datetime.now().time())