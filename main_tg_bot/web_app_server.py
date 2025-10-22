# web_app_server.py
from flask import Flask, render_template, request, jsonify
import os
import threading
import time
import ssl

# Импортируем нашу функцию генерации SSL
from ssl_generator import generate_ssl_certificates_force, check_ssl_files

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


def run_web_server():
    """Запуск веб-сервера с локальным HTTPS"""
    global web_app_public_url, web_server_ready

    try:
        print("🔐 Настройка локального HTTPS сервера...")

        # Проверяем и генерируем SSL сертификаты если нужно
        if not generate_ssl_certificates_force():
            print("❌ Не удалось настроить SSL сертификаты")
            web_server_ready = False
            web_server_started_event.set()
            return

        # Проверяем что файлы существуют
        if not check_ssl_files():
            print("❌ SSL файлы не созданы")
            web_server_ready = False
            web_server_started_event.set()
            return

        # Пути к SSL сертификатам
        ssl_cert = "lapkabookink.com+3.pem"
        ssl_key = "lapkabookink.com+3-key.pem"

        # Создаем SSL контекст
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(ssl_cert, ssl_key)

        # Устанавливаем публичный URL
        web_app_public_url = f"https://lapkabookink.com:5000"
        web_server_ready = True
        web_server_started_event.set()

        print(f"✅ Локальный HTTPS сервер создан: {web_app_public_url}")
        print("🤖 Теперь можно использовать Web App в Telegram!")

        # Запускаем Flask сервер с HTTPS
        app.run(
            host='lapkabookink.com',  # Используем доменное имя
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