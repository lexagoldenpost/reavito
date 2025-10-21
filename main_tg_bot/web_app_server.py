# web_app_server.py
from flask import Flask, render_template, request, jsonify
import os
import threading
import time
import ssl
import subprocess
import sys

app = Flask(__name__, template_folder='html')


# Добавляем middleware для обработки CORS и заголовков
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


# Глобальные переменные
web_app_public_url = None
web_server_thread = None
web_server_ready = False
web_server_started_event = threading.Event()


@app.route('/booking-form')
def booking_form():
    """Страница формы бронирования"""
    object_id = request.args.get('object', '')
    user_id = request.args.get('user_id', '')

    return render_template('booking_form.html',
                           object_id=object_id,
                           user_id=user_id)


@app.route('/health')
def health_check():
    """Проверка готовности сервера"""
    return jsonify({"status": "ready"})


def is_mkcert_available():
    """Проверяет, доступен ли mkcert в системе"""
    try:
        result = subprocess.run(['mkcert', '-version'],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def setup_mkcert_ssl():
    """Настройка SSL с использованием mkcert сертификатов"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Проверяем доступность mkcert
        if not is_mkcert_available():
            print("❌ mkcert не найден в системе")
            print_mkcert_installation_instructions()
            return None

        # Ищем существующие сертификаты mkcert
        cert_files = [
            "localhost+2.pem",  # Стандартное имя от mkcert
            "localhost.pem",  # Альтернативное имя
        ]

        key_files = [
            "localhost+2-key.pem",
            "localhost-key.pem",
        ]

        cert_path = None
        key_path = None

        # Ищем существующие сертификаты
        for cert_file in cert_files:
            potential_cert = os.path.join(current_dir, cert_file)
            if os.path.exists(potential_cert):
                cert_path = potential_cert
                break

        for key_file in key_files:
            potential_key = os.path.join(current_dir, key_file)
            if os.path.exists(potential_key):
                key_path = potential_key
                break

        # Если не нашли, создаем через mkcert
        if not cert_path or not key_path:
            print("🔍 Сертификаты mkcert не найдены, создаем новые...")
            if not generate_mkcert_certificates():
                return None
            # После генерации используем стандартные имена
            cert_path = os.path.join(current_dir, "localhost+2.pem")
            key_path = os.path.join(current_dir, "localhost+2-key.pem")

        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            print("❌ Файлы сертификатов не найдены после генерации")
            return None

        print(f"✅ Используем SSL сертификаты mkcert:")
        print(f"   Cert: {os.path.basename(cert_path)}")
        print(f"   Key: {os.path.basename(key_path)}")

        # Создаем SSL контекст
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        print("✅ SSL контекст создан успешно")
        return context

    except Exception as e:
        print(f"❌ Ошибка настройки SSL с mkcert: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_mkcert_certificates():
    """Генерация сертификатов через mkcert"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))

        print("🔄 Генерация сертификатов mkcert...")

        # Сначала устанавливаем CA
        print("📥 Установка локального Certificate Authority...")
        ca_result = subprocess.run(['mkcert', '-install'],
                                   capture_output=True, text=True, cwd=current_dir)

        if ca_result.returncode != 0:
            print(f"❌ Ошибка установки CA: {ca_result.stderr}")
            return False

        print("✅ Локальный CA установлен")

        # Создаем сертификаты для localhost
        print("📄 Создание сертификатов для localhost...")
        cert_result = subprocess.run(['mkcert', 'localhost', '127.0.0.1', '::1'],
                                     capture_output=True, text=True, cwd=current_dir)

        if cert_result.returncode == 0:
            print("✅ Сертификаты успешно созданы")
            print(cert_result.stdout)
            return True
        else:
            print(f"❌ Ошибка создания сертификатов: {cert_result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Не удалось выполнить mkcert: {e}")
        return False


def print_mkcert_installation_instructions():
    """Печатает инструкции по установке mkcert"""
    print("\n" + "=" * 60)
    print("📋 ИНСТРУКЦИЯ ПО УСТАНОВКЕ MKCert")
    print("=" * 60)
    print("Для работы Telegram Web App требуется HTTPS.")
    print("Установите mkcert одним из способов:")
    print()
    print("🪟 Windows:")
    print("   1. Скачайте с https://github.com/FiloSottile/mkcert/releases")
    print("   2. Или через Chocolatey: choco install mkcert")
    print()
    print("🍎 macOS:")
    print("   brew install mkcert")
    print()
    print("🐧 Linux (Ubuntu/Debian):")
    print("   sudo apt install libnss3-tools")
    print("   wget https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v1.4.4-linux-amd64")
    print("   chmod +x mkcert-v1.4.4-linux-amd64")
    print("   sudo mv mkcert-v1.4.4-linux-amd64 /usr/local/bin/mkcert")
    print()
    print("После установки перезапустите бота.")
    print("=" * 60 + "\n")


def create_fallback_ssl():
    """Создание fallback SSL контекста без mkcert"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        cert_file = os.path.join(current_dir, "cert.pem")
        key_file = os.path.join(current_dir, "key.pem")

        # Пробуем создать простые самоподписанные сертификаты
        print("🔄 Попытка создания самоподписанных сертификатов...")

        # Используем упрощенный подход с Python
        import tempfile
        import atexit

        # Создаем временные сертификаты
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta

        # Генерируем ключ
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Создаем сертификат
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Booking Bot"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).sign(private_key, hashes.SHA256())

        # Сохраняем ключ
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        # Сохраняем сертификат
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print("✅ Самоподписанные сертификаты созданы")

        # Создаем SSL контекст
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        return context

    except ImportError:
        print("❌ Не удалось создать самоподписанные сертификаты")
        print("   Установите: pip install cryptography")
        return None
    except Exception as e:
        print(f"❌ Ошибка создания самоподписанных сертификатов: {e}")
        return None


def run_web_server():
    """Запуск веб-сервера"""
    global web_app_public_url, web_server_ready

    try:
        print("Запуск локального HTTPS веб-сервера...")

        # Пробуем сначала mkcert, потом fallback
        ssl_context = setup_mkcert_ssl()
        if ssl_context is None:
            print("🔄 Пробуем создать самоподписанные сертификаты...")
            ssl_context = create_fallback_ssl()

        if ssl_context is None:
            print("❌ Не удалось настроить SSL, запускаем без HTTPS...")
            web_app_public_url = "http://localhost:5000"
            web_server_ready = True
            web_server_started_event.set()

            print("⚠️  ВНИМАНИЕ: Запуск без HTTPS!")
            print("   Telegram Web App требует HTTPS для работы!")
            print("   Функциональность Web App будет ограничена!")

            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        else:
            web_app_public_url = "https://localhost:5000"
            web_server_ready = True
            web_server_started_event.set()

            print(f"✅ Локальный HTTPS сервер запущен: {web_app_public_url}")
            print("🔒 Используются SSL сертификаты")

            app.run(
                host='0.0.0.0',
                port=5000,
                debug=False,
                use_reloader=False,
                ssl_context=ssl_context
            )

    except Exception as e:
        print(f"❌ Ошибка запуска веб-сервера: {e}")
        import traceback
        traceback.print_exc()
        web_server_ready = False
        web_server_started_event.set()


# Остальные функции остаются без изменений
def start_web_server():
    """Запуск веб-сервера и ожидание готовности"""
    global web_server_thread, web_server_ready, web_server_started_event

    if web_server_thread is None or not web_server_thread.is_alive():
        web_server_ready = False
        web_server_started_event.clear()
        web_server_thread = threading.Thread(target=run_web_server, daemon=True)
        web_server_thread.start()

        # Ждем готовности сервера с таймаутом
        max_wait_time = 30
        server_ready = web_server_started_event.wait(timeout=max_wait_time)

        if server_ready and web_server_ready and web_app_public_url:
            print(f"✅ Веб-сервер запущен: {web_app_public_url}")
            return web_app_public_url
        else:
            print("❌ Не удалось запустить веб-сервер в течение заданного времени")
            return None
    else:
        print("ℹ️ Веб-сервер уже запущен")
        return web_app_public_url


def stop_web_server():
    """Остановка веб-сервера"""
    global web_server_ready, web_server_started_event
    try:
        web_server_ready = False
        web_server_started_event.clear()
        print("✅ Веб-сервер остановлен")
    except Exception as e:
        print(f"❌ Ошибка остановки веб-сервера: {e}")


def get_web_app_url():
    """Получить публичный URL для Web App"""
    global web_app_public_url, web_server_ready

    if web_server_ready and web_app_public_url:
        return web_app_public_url
    else:
        raise Exception("Web server not ready")


def wait_for_web_server(timeout=30):
    """Ожидание готовности веб-сервера"""
    return web_server_started_event.wait(timeout=timeout)