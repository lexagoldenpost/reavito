from sqlalchemy import create_engine, Column, Integer, String, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json
import logging
import os
from dotenv import load_dotenv
logging.basicConfig(level=logging.DEBUG, filename="avito_webhook.log",filemode="w")

# Загрузка переменных из .env файла
load_dotenv()

DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
# 1. Подключение к PostgreSQL
DATABASE_URL = f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@localhost:5432/{DB_NAME}'
engine = create_engine(DATABASE_URL)


# 2. Создание базового класса для моделей
Base = declarative_base()

# 3. Определение модели таблицы
class Avito_Msg(Base):
    __tablename__ = 'avito_chat'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    item_id = Column(String)
    author_id = Column(String)
    avito_user_id = Column(String)
    content = Column(String)
    is_send_ii = Column(Boolean)  # Поле для хранения JSON-данных

# 4. Создание таблицы в базе данных
Base.metadata.create_all(engine)

# 5. Создание сессии для работы с базой данных
Session = sessionmaker(bind=engine)
session = Session()

# 6. Загрузка данных из JSON
def save_db(chat_id, item_id, author_id, avito_user_id, content) :
    #data = json.loads(json_data)
    # 7. Добавление данных в таблицу
    new_avito_msg= Avito_Msg(
        chat_id=chat_id,
        item_id=item_id,
        author_id=author_id,
        avito_user_id=avito_user_id,
        content=content,
        is_send_ii=True
    )
    session.add(new_avito_msg)

    # 8. Сохранение изменений в базе данных
    session.commit()
    # 9. Закрытие сессии
    session.close()
    logging.info(f"Данные успешно добавлены в таблицу")