# web_app_server.py
from flask import Flask, render_template, request, jsonify
import os
import threading
import time
from pyngrok import ngrok, conf

app = Flask(__name__, template_folder='html')

# Добавляем middleware для обработки CORS и заголовков
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('ngrok-skip-browser-warning', 'true')
    return response

@app.before_request
def before_request():
    # Добавляем заголовки для обхода предупреждения ngrok
    if 'ngrok-skip-browser-warning' not in request.headers:
        # Можно добавить логику для проверки реферера или других параметров
        pass

# Глобальные переменные
web_app_public_url = None
web_server_thread = None
web_server_ready = False
web_server_started_event = threading.Event()  # Добавляем Event для синхронизации


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


def setup_ngrok():
    """Настройка ngrok"""
    try:
        auth_token = "34NZhvdSiANNpDgvo97c25tFmwG_5SW3wHvBV7HDVbCmDVjp8"
        conf.get_default().auth_token = auth_token
        print("✅ Ngrok настроен")
    except Exception as e:
        print(f"❌ Ошибка настройки ngrok: {e}")


def run_web_server():
    """Запуск веб-сервера"""
    global web_app_public_url, web_server_ready

    try:
        setup_ngrok()
        print("Запуск веб-сервера для Web App...")

        # Создаем туннель
        public_url = ngrok.connect(5000, bind_tls=True).public_url
        web_app_public_url = public_url
        web_server_ready = True
        web_server_started_event.set()  # Сигнализируем, что сервер запущен

        print(f"✅ Ngrok туннель создан: {public_url}")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Ошибка запуска веб-сервера: {e}")
        web_server_ready = False
        web_server_started_event.set()  # Все равно сигнализируем, даже при ошибке


def start_web_server():
    """Запуск веб-сервера и ожидание готовности"""
    global web_server_thread, web_server_ready, web_server_started_event

    if web_server_thread is None or not web_server_thread.is_alive():
        web_server_ready = False
        web_server_started_event.clear()  # Сбрасываем событие
        web_server_thread = threading.Thread(target=run_web_server, daemon=True)
        web_server_thread.start()

        # Ждем готовности сервера с таймаутом
        max_wait_time = 30  # Увеличиваем время ожидания
        server_ready = web_server_started_event.wait(timeout=max_wait_time)

        if server_ready and web_server_ready and web_app_public_url:
            print(f"✅ Веб-сервер запущен через ngrok: {web_app_public_url}")
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
        ngrok.disconnect(5000)
        ngrok.kill()
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