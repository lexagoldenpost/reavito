# main.py
import logging
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Загрузка переменных из .env файла
load_dotenv()


# Секретный ключ из кабинета Avito
AVITO_SECRET = os.getenv('AVITO_CLIENT_SECRET')
# БД
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Путь к папке для логов
log_dir = "logs"
log_file = os.path.join(log_dir, "avito_chat_in.log")

# Создаем папку для логов, если она не существует
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Настройка логгера
def setup_logger():
    # Создаем логгер
    logger = logging.getLogger("avito_chat_in")
    logger.setLevel(logging.DEBUG)

    # Создаем RotatingFileHandler для ротации по размеру
    handler = RotatingFileHandler(
        log_file,  # Имя файла
        maxBytes=1024 * 1024,  # Максимальный размер файла (1 МБ)
        backupCount=5,  # Количество backup-файлов
    )

    # Формат логов
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # Добавляем обработчик к логгеру
    logger.addHandler(handler)

    return logger

def setup_db() :
    # 1. Подключение к PostgreSQL
    DATABASE_URL = f'postgresql+psycopg2://{main.DB_USER}:{main.DB_PASSWORD}@localhost:5432/{main.DB_NAME}'
    engine = create_engine(DATABASE_URL)

    # 2. Создание базового класса для моделей
    Base = declarative_base()

    # 3. Определение модели таблицы
    class Avito_Msg(Base):
        __tablename__ = 'avito_chat'
        msg_id = Column(String, primary_key=True)
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

# Инициализация логгера
logger = setup_logger()
db = setup_db()

# Пример использования логгера в основном модуле
logger.info("Основной модуль приема авито сообщений: Логгер настроен и готов к использованию.")