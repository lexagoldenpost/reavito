# create_session.py
import asyncio
import sys
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession

# Добавляем путь к проекту для импорта конфигов
project_root = Path(__file__).parent
sys.path.append(str(project_root))


async def create_telegram_session():
    """Создание строки сессии для нового аккаунта"""
    print("=" * 60)
    print("СОЗДАНИЕ НОВОЙ СЕССИИ TELEGRAM")
    print("=" * 60)

    # Запрашиваем данные у пользователя
    print("\n1. Введите данные из https://my.telegram.org/apps:")
    api_id = input("API ID: ").strip()
    api_hash = input("API Hash: ").strip()

    print("\n2. Введите данные аккаунта:")
    phone = input("Номер телефона (с кодом страны, например +79154556189): ").strip()

    # Создаем сессию в памяти
    session = StringSession()

    # Создаем клиента
    client = TelegramClient(
        session=session,
        api_id=int(api_id),
        api_hash=api_hash,
        system_version='4.16.30-vxCUSTOM',
        device_model='Python Device',
        app_version='1.0.0'
    )

    try:
        # Подключаемся
        print("\n📡 Подключаемся к Telegram...")
        await client.connect()

        # Отправляем запрос на код
        print("📱 Отправляем запрос на код...")
        sent_code = await client.send_code_request(phone)

        # Получаем тип кода (SMS, Telegram и т.д.)
        code_type = sent_code.type.__class__.__name__
        print(f"📟 Код будет отправлен через: {code_type}")

        # Запрашиваем код
        code = input("\nВведите код из Telegram/SMS: ").strip()

        try:
            # Пробуем войти с кодом
            await client.sign_in(phone=phone, code=code)
            print("✅ Вход по коду успешен!")

        except Exception as e:
            if "password" in str(e).lower():
                # Требуется пароль 2FA
                print("🔒 Требуется пароль двухфакторной аутентификации")
                password = input("Введите пароль 2FA: ").strip()
                await client.sign_in(password=password)
                print("✅ Вход с паролем успешен!")
            else:
                raise e

        # Получаем строку сессии
        session_string = session.save()

        print("\n" + "=" * 60)
        print("✅ СЕССИЯ СОЗДАНА УСПЕШНО!")
        print("=" * 60)

        # Получаем информацию об аккаунте
        me = await client.get_me()
        print(f"\n👤 Информация об аккаунте:")
        print(f"   Имя: {me.first_name} {me.last_name or ''}")
        print(f"   ID: {me.id}")
        print(f"   Username: @{me.username}" if me.username else "   Username: отсутствует")
        print(f"   Телефон: {me.phone}")

        print("\n📋 СТРОКА СЕССИИ (СОХРАНИТЕ!):")
        print("-" * 60)
        print(session_string)
        print("-" * 60)

        # Сохраняем в разные форматы
        session_dir = project_root / "sessions"
        session_dir.mkdir(exist_ok=True)

        # 1. В файл session_string.txt
        with open(session_dir / "session_string.txt", "w", encoding="utf-8") as f:
            f.write(session_string)

        # 2. В файл session_info.txt с деталями
        with open(session_dir / "session_info.txt", "w", encoding="utf-8") as f:
            f.write(f"Phone: {phone}\n")
            f.write(f"API ID: {api_id}\n")
            f.write(f"API Hash: {api_hash}\n")
            f.write(f"Account: {me.first_name} {me.last_name or ''}\n")
            f.write(f"User ID: {me.id}\n")
            f.write(f"Username: {me.username or 'N/A'}\n")
            f.write(f"\nSession String:\n{session_string}\n")

        # 3. В формате для конфига
        with open(session_dir / "config_format.txt", "w", encoding="utf-8") as f:
            f.write(f'TELEGRAM_SESSION_STRING = "{session_string}"\n')

        print(f"\n💾 Сессия сохранена в:")
        print(f"   • {session_dir / 'session_string.txt'}")
        print(f"   • {session_dir / 'session_info.txt'}")
        print(f"   • {session_dir / 'config_format.txt'}")

        print("\n📝 Для использования добавьте в common/config.py:")
        print(f'TELEGRAM_SESSION_STRING = "{session_string}"')

        return session_string

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nВозможные причины:")
        print("1. Неверный код (действует 5 минут)")
        print("2. Неверный пароль 2FA")
        print("3. Проблемы с подключением")
        return None

    finally:
        await client.disconnect()
        print("\n🔌 Подключение закрыто")


if __name__ == "__main__":
    asyncio.run(create_telegram_session())