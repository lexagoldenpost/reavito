# models.py
from sqlalchemy import Column, String, Integer, Date, Text, Time, DateTime, \
  Boolean, LargeBinary, func

from common.database import Base


class Booking(Base):
  __tablename__ = 'booking'
  __table_args__ = {'extend_existing': True}  # Добавляем эту строку

  id = Column(Integer, primary_key=True)
  sheet_name = Column(String(50))
  guest = Column(String(100))
  booking_date = Column(Date)
  check_in = Column(Date)
  check_out = Column(Date)
  nights = Column(String(20))
  amount_by_month = Column(Text)
  total_amount = Column(Text)
  deposit = Column(String(100))
  balance = Column(String(100))
  source = Column(String(50))
  additional_payments = Column(Text)
  expenses = Column(Text)
  payment_method = Column(String(50))
  comments = Column(Text)
  phone = Column(String(100))
  additional_phone = Column(String(100))
  flights = Column(Text)


class Notification(Base):
  __tablename__ = 'notifications'
  __table_args__ = {'extend_existing': True}  # Добавляем эту строку

  id = Column(Integer, primary_key=True)
  notification_type = Column(String)
  start_time = Column(Time)
  trigger_object = Column(String)
  send_if_new = Column(String)
  trigger_column = Column(String)
  trigger_days = Column(Integer)
  message = Column(Text)
  last_updated = Column(DateTime)

class Chat(Base):
  __tablename__ = 'chats'
  __table_args__ = {'extend_existing': True}

  id = Column(Integer, primary_key=True)
  chat_name = Column(String(100), nullable=False)  # Наименование чата
  send_frequency = Column(Integer)  # Периодичность отправки в днях
  accepts_images = Column(Boolean)  # Картинки принимает (Да/Нет)
  chat_object = Column(String(100))  # Новый столбец: Объект
  last_updated = Column(DateTime)  # Когда последний раз обновлялась запись
  last_send = Column(DateTime)  # Когда последний раз обновлялась отправлялась
  channel_name = Column(String)  #  Наименвоение чата

class ChannelKeyword(Base):
  __tablename__ = 'channel_keyword'
  __table_args__ = {'extend_existing': True}

  id = Column(Integer, primary_key=True)
  channel = Column(String, nullable=False)  # Наименование канала или групп
  keywords = Column(String, nullable=False)  # ключевые слова
  last_updated = Column(DateTime)  # Когда последний раз обновлялась запись
  channel_names = Column(String)  # Наименвоение чата


class TelethonSession(Base):
  __tablename__ = 'telethon_sessions'
  __table_args__ = {'extend_existing': True}

  id = Column(Integer, primary_key=True)
  session_id = Column(String(255), nullable=False, unique=True)
  dc_id = Column(Integer)
  server_address = Column(String(255))
  port = Column(Integer)
  auth_key = Column(LargeBinary)
  takeout_id = Column(Integer)
  update_state = Column(LargeBinary)
  pts = Column(Integer)
  qts = Column(Integer)
  date = Column(DateTime)
  seq = Column(Integer)
  created_at = Column(DateTime, server_default=func.now())
  updated_at = Column(DateTime, onupdate=func.now())
  session_string=Column(Text)  # Сериализованная сессия в base64