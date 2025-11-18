# get_session.py
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from common.config import Config


def get_new_session():
    # Используйте нужные API ID и HASH
    api_id = Config.TELEGRAM_API_SEND_BOOKING_ID  # или другой API ID
    api_hash = Config.TELEGRAM_API_SEND_BOOKING_HASH  # или другой API HASH
    phone = Config.TELEGRAM_SEND_BOOKING_PHONE  # или другой телефон

    # Создаем клиент с пустой сессией
    client = TelegramClient(StringSession(), api_id, api_hash, system_version='4.16.30-vxCUSTOM')

    try:
        client.connect()

        # Проверяем, авторизован ли пользователь
        if not client.is_user_authorized():
            print(f"Отправка кода подтверждения на {phone}...")
            client.send_code_request(phone)

            # Вводим код подтверждения
            code = input('Введите код подтверждения: ')
            client.sign_in(phone, code)

        # Получаем строку сессии
        session_string = client.session.save()
        print(f"✅ НОВАЯ СТРОКА СЕССИИ:")
        print(session_string)
        print("=" * 50)
        print("Скопируйте эту строку и добавьте в .env файл как TELEGRAM_STRING_SESSION")

        # Также можно получить информацию о пользователе
        me = client.get_me()
        print(f"Пользователь: {me.first_name} {me.last_name} (ID: {me.id})")
        print(f"Телефон: {me.phone}")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    get_new_session()