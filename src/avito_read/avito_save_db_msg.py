from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import main




# 6. Загрузка данных из JSON
def save_db(msg_id, chat_id, item_id, author_id, avito_user_id, content) :
    #data = json.loads(json_data)
    # 7. Добавление данных в таблицу
    new_avito_msg= main.Avito_Msg(
        msg_id=msg_id,
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

    main.logging.info(f"Данные успешно добавлены в таблицу")