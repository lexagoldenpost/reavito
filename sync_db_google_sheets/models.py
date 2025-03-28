# models.py
from sqlalchemy import Column, String, Integer, Float, Date, Text, Time, DateTime
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
  trigger_days = Column(Float)
  message = Column(Text)
  last_updated = Column(DateTime)